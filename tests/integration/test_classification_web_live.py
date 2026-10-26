"""Real PostgreSQL -> FastAPI -> Vite -> Chromium classification acceptance.

Run only against the disposable settings.test_database_url, without concurrent
integration suites (the repository db_engine fixture rebuilds its schemas).
Requires frontend npm dependencies and a Playwright Chromium/Chrome installation.
No browser route interception or development database connection is used.
"""


# ruff: noqa: E501 -- Embedded browser script follows JavaScript formatting.

import asyncio
import datetime as dt
import json
import os
import shutil
import socket
import subprocess
import threading
import time
import urllib.request
from pathlib import Path

import pytest
import uvicorn
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from fip.api.app import create_app
from fip.api.auth import get_principal
from fip.api.context import Principal
from fip.api.dependencies import get_api_repositories
from fip.api.repositories import ApiRepositories
from fip.services.data_service.classification import (
    ClassificationSnapshot,
    DimensionResult,
    normalize_evidence,
)
from fip.services.data_service.classification.service import ClassificationService
from fip.services.data_service.models.fund import Fund, FundClassificationReviewCase, FundShareClass
from fip.settings import settings

pytestmark = pytest.mark.integration
ROOT = Path(__file__).resolve().parents[2]


def _port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _wait(url, process=None):
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if process is not None and process.poll() is not None:
            raise AssertionError("Vite exited before becoming ready")
        try:
            with urllib.request.urlopen(url, timeout=1):
                return
        except (OSError, TimeoutError):
            time.sleep(0.1)
    raise AssertionError(f"Server did not become ready: {url}")


def test_real_browser_classification_review_and_historical_visibility(db_session, tmp_path):
    assert db_session.bind is not None
    assert db_session.bind.engine.url.database == settings.test_database_url.rsplit("/", 1)[-1]
    assert shutil.which("node"), "Install Node.js and run make frontend-install"
    assert (ROOT / "frontend/node_modules/@playwright/test").exists()
    at = dt.datetime(2026, 1, 1, tzinfo=dt.UTC)
    fund = Fund(
        fund_code="CLASS-WEB-LIVE", product_name="真实浏览器分类验收", grouping_status="CONFIRMED"
    )
    db_session.add(fund)
    db_session.flush()
    db_session.add(
        FundShareClass(
            fund_id=fund.id,
            share_class_code="A",
            display_name="真实浏览器分类验收A",
            inception_date=dt.date(2020, 1, 1),
        )
    )
    proof = normalize_evidence(
        source="OFFICIAL",
        field="asset_class",
        value="EQUITY",
        classified_at=at,
        locator="测试招募书第1页",
    )

    def confirmed(value):
        return DimensionResult(status="CONFIRMED", value=value, evidence=(proof,))

    snapshot = ClassificationSnapshot(
        asset_class=confirmed("EQUITY"),
        strategy=DimensionResult(status="CANDIDATE", candidates=("ACTIVE",), evidence=(proof,)),
        geography=confirmed(("DOMESTIC",)),
        product_structure=confirmed("ORDINARY"),
        market_attributes=confirmed(("DOMESTIC",)),
    )
    revision = ClassificationService(db_session).write(
        fund.id,
        snapshot,
        valid_from=at.date(),
        available_at=at,
        actor="browser-seed",
        reason="独立测试夹具",
    )
    case = db_session.scalars(
        select(FundClassificationReviewCase).where(
            FundClassificationReviewCase.revision_id == revision.id
        )
    ).one()
    # Flush IDs on the pytest thread; all subsequent SQL is serialized by the
    # test-only HTTP middleware because this fixture owns one savepoint session.
    case_id, revision_id, fund_code = case.id, revision.id, fund.fund_code
    db_session.flush()
    api_port, vite_port = _port(), _port()
    app = create_app(
        settings_override=settings.model_copy(
            update={"database_url": settings.test_database_url, "rate_limit_per_minute": 1000}
        ),
        strict_contracts=True,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[f"http://127.0.0.1:{vite_port}"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    lock = asyncio.Lock()
    principal = Principal("browser-reviewer", ("Reviewer",), True, True)

    @app.middleware("http")
    async def isolate_session(request, call_next):
        async with lock:
            request.state.verified_principal = principal
            return await call_next(request)

    app.dependency_overrides[get_principal] = lambda: principal
    app.dependency_overrides[get_api_repositories] = lambda: ApiRepositories.from_session(
        db_session
    )
    server = uvicorn.Server(
        uvicorn.Config(app, host="127.0.0.1", port=api_port, log_level="warning")
    )
    thread = threading.Thread(target=server.run, daemon=True)
    vite = None
    log_path = tmp_path / "vite.log"
    try:
        thread.start()
        _wait(f"http://127.0.0.1:{api_port}/openapi.json")
        with log_path.open("w") as log:
            vite = subprocess.Popen(
                [
                    "node",
                    "node_modules/vite/bin/vite.js",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(vite_port),
                    "--strictPort",
                ],
                cwd=ROOT / "frontend",
                env={**os.environ, "VITE_API_BASE_URL": f"http://127.0.0.1:{api_port}"},
                stdout=log,
                stderr=subprocess.STDOUT,
            )
            _wait(f"http://127.0.0.1:{vite_port}", vite)
            script = tmp_path / "classification-live.cjs"
            script.write_text(NODE_SCRIPT)
            payload = {
                "web": f"http://127.0.0.1:{vite_port}",
                "api": f"http://127.0.0.1:{api_port}",
                "caseId": case_id,
                "revisionId": revision_id,
                "fundCode": fund_code,
                "playwright": str(ROOT / "frontend/node_modules/@playwright/test"),
                "channel": os.environ.get(
                    "PLAYWRIGHT_CHANNEL", "chrome" if os.uname().sysname == "Darwin" else ""
                ),
            }
            result = subprocess.run(
                ["node", str(script), json.dumps(payload)],
                capture_output=True,
                text=True,
                timeout=90,
            )
            assert result.returncode == 0, result.stdout + result.stderr + log_path.read_text()
            assert "LIVE_CLASSIFICATION_OK" in result.stdout
    finally:
        if vite is not None:
            vite.terminate()
            try:
                vite.wait(timeout=10)
            except subprocess.TimeoutExpired:
                vite.kill()
                vite.wait(timeout=5)
        server.should_exit = True
        thread.join(timeout=10)
        assert not thread.is_alive(), "Test HTTP server failed to stop"


NODE_SCRIPT = r"""
const config = JSON.parse(process.argv[2]);
const { chromium, expect } = require(config.playwright);
(async () => {
  const browser = await chromium.launch(config.channel ? {channel: config.channel} : {});
  try {
    const context = await browser.newContext({extraHTTPHeaders:{'X-Roles':'Reviewer'}});
    const page = await context.newPage();
    const failures = [];
    const apiResponses = [];
    page.on('response', async response => {
      if (response.url().includes('/api/v1/')) {
        try { apiResponses.push({url:response.url(), status:response.status(), body:await response.text()}); } catch {}
      }
    });
    page.on('requestfailed', request => failures.push(request.url() + ': ' + request.failure()?.errorText));
    page.on('pageerror', error => failures.push(error.message));
    const get = async path => {
      const response = await context.request.get(config.api + path);
      expect(response.status(), await response.text()).toBe(200);
      return response.json();
    };
    const historyPath = `/api/v1/funds/${config.fundCode}/classification-history?decision_at=2026-01-01`;
    const session = await get('/api/v1/session');
    expect(session.data.capabilities.can_review_classifications).toBe(true);
    const baselineCase = await get(`/api/v1/classification-reviews/${config.caseId}`);
    expect(baselineCase.data.status).toBe('PENDING');
    const oldHistory = await get(historyPath);
    const oldDetail = await get(`/api/v1/funds/${config.fundCode}?as_of_date=2026-01-01`);
    await page.goto(config.web + '/funds');
    await page.getByRole('textbox',{name:'基金名称',exact:true}).fill('真实浏览器分类验收');
    for (const [label, value] of [['资产类别','EQUITY'],['投资策略','UNKNOWN'],['投资地域','DOMESTIC'],['产品结构','ORDINARY'],['市场属性','DOMESTIC'],['分类状态','CANDIDATE']]) {
      await page.getByRole('listbox',{name:label,exact:true}).selectOption([value]);
    }
    // Candidate ACTIVE must not match confirmed-value filtering; use UNKNOWN
    // only for the dimension status query below, then remove strategy filter.
    await page.getByRole('listbox',{name:'投资策略',exact:true}).selectOption([]);
    await page.getByRole('button',{name:'查询',exact:true}).click();
    await expect(page).toHaveURL(/asset_class=EQUITY/);
    await page.getByRole('link',{name:'真实浏览器分类验收',exact:true}).click();
    await expect(page.getByLabel('五维分类').first()).toContainText('CANDIDATE');
    await expect(page.getByLabel('资产类别证据').first()).toContainText('测试招募书第1页');
    await page.getByText('可见分类历史',{exact:true}).click();
    await expect(page.getByRole('heading',{name:`修订 ${config.revisionId} / v1`,exact:true})).toBeVisible();
    await page.goto(config.web + `/classification-reviews?case=${config.caseId}`);
    try {
      await page.getByRole('form',{name:'分类复核',exact:true}).waitFor({timeout:15000});
    } catch (error) {
      throw new Error(String(error) + '\nPAGE: ' + await page.locator('body').innerText() + '\nAPI: ' + JSON.stringify(apiResponses) + '\nERRORS: ' + JSON.stringify(failures));
    }
    await page.getByRole('combobox',{name:/^复核维度/}).selectOption('strategy');
    await page.getByRole('combobox',{name:/^决定值/}).selectOption('ACTIVE');
    await page.getByLabel('复核理由',{exact:true}).fill('浏览器人工确认正式策略资料');
    await page.getByLabel('证据原文',{exact:true}).fill('采用主动投资策略');
    await page.getByLabel('资料定位',{exact:true}).fill('测试招募书策略章节第3页');
    const posted = page.waitForResponse(response => response.request().method()==='POST' && response.url().endsWith(`/classification-reviews/${config.caseId}/review`));
    await page.getByRole('button',{name:'提交复核',exact:true}).click();
    const submitted = await posted;
    expect(submitted.status(), await submitted.text()).toBe(200);
    await expect(page.getByRole('status')).toContainText('复核已保存');
    await page.goto(config.web + '/funds?asset_class=EQUITY&strategy=ACTIVE&geography=DOMESTIC&product_structure=ORDINARY&market_attributes=DOMESTIC&classification_status=CONFIRMED');
    await page.getByRole('link',{name:'真实浏览器分类验收',exact:true}).click();
    await expect(page.getByLabel('五维分类').first()).toContainText('CONFIRMED · 最终值 ACTIVE');
    const current = await get(`/api/v1/funds/${config.fundCode}`);
    expect(current.data.classification.revision_id).not.toBe(config.revisionId);
    expect(current.data.classification.strategy.value).toBe('ACTIVE');
    expect((await get(historyPath)).data).toEqual(oldHistory.data);
    expect((await get(`/api/v1/funds/${config.fundCode}?as_of_date=2026-01-01`)).data.classification).toEqual(oldDetail.data.classification);
    await page.goto(config.web + `/funds/${config.fundCode}?as_of_date=2026-01-01`);
    await expect(page.getByLabel('五维分类').first()).toContainText(`修订 ${config.revisionId} / v1`);
    await expect(page.getByLabel('五维分类').first()).toContainText('CANDIDATE');
    expect(failures).toEqual([]);
    console.log('LIVE_CLASSIFICATION_OK');
  } finally { await browser.close(); }
})().catch(error=>{ console.error(error); process.exitCode=1; });
"""
