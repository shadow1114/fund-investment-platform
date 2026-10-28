# Classification live sample acceptance (2026-10-28)

## Scope

This is a bounded, read-only smoke acceptance authorized for the disposable `fip_test` database at `localhost:5432`. It samples fund-specific source records only; it does not fetch a full fund universe or full index membership set, and it does not write business records. Raw sample payloads and the collection manifest are kept outside the repository at `/tmp/fip-classification-golden-20261028`.

The sample includes up to five attempted fund codes for each strategy category. Source calls used the existing isolated AkShare adapter. Two Snowball detail requests failed (`510300` and `560100`, `KeyError: 'data'`); their EastMoney overview records were available. Alternate codes were sampled for those categories.

## Results

| Expected category | Fund | Asset result | Strategy result | Notes |
|---|---:|---|---|---|
| Passive index | 000051 | EQUITY confirmed | UNKNOWN | Tracking target alone is insufficient; exact index membership was not fetched. |
| Enhanced index | 001050 | EQUITY confirmed | ENHANCED_INDEX confirmed | The source text identifies index enhancement. |
| Target date | 007668 | FOF confirmed | TARGET_DATE confirmed | Official product page identifies a 2035 target-date fund. |
| Target risk | 006294 | FOF confirmed | TARGET_RISK confirmed | Official report identifies a stable target-risk strategy. |
| Active | 090016 | MIXED confirmed | ACTIVE confirmed | Official prospectus explicitly describes an active investment strategy. |

The live sample exposed a false positive in the QUANTITATIVE tag: `数量化定价模型` occurred in a supporting-asset valuation clause, unrelated to the fund's overall quantitative investment approach. The `QUANT_METHOD` matcher was narrowed to require strategy-related wording after `数量化`, and a regression test was added. Replaying the representative sample after the fix changed 007668's QUANTITATIVE tag from CONFIRMED to UNKNOWN; its TARGET_DATE result remained confirmed. UNKNOWN is the expected conservative outcome where no qualifying quantitative adoption statement exists.

The collector manifest records initial classifications before that regex correction. Use the post-fix replay described above for the final tag result. Individual payloads, collection timestamps, and SHA-256 values are in the temporary manifest and files listed above; raw strategy text is intentionally not copied into this report.

## Source cross-checks

- [Guangfa 007668 product page](https://www.gffunds.com.cn/funds/?fundcode=007668) identifies it as a target-date fund with a 2035 date.
- [Wanjia 006294 product page](https://www.wjasset.com/products/fof/006294/index.html) identifies the product as a stable target-risk strategy fund.
- [99fund 001050 product page](https://www.99fund.com/main/products/pofund/001050/fundgg.shtml) identifies it as the CSI 500 enhanced index fund.
- [ICBC fund page for 000051](https://www.icbc.com.cn/webpage/fund/fundindex?fundId=000051) identifies the product as a CSI 300 ETF feeder fund. Runtime classification remains UNKNOWN until exact, verified membership evidence is loaded.
- [Dacheng 090016 annual report](https://www.dcfund.com.cn/plat_files/upload/ann_upload/20260421/202604211776765224117.pdf) explicitly describes an active investment strategy.

These links are source cross-checks, not an independent human research signoff. Final human review remains outstanding.

## Verification and limits

- Offline focused Python acceptance passed after the fix (12 focused suites; 434 tests before the added regression, plus the new strategy regression suite). The full strategy v3 suite, Ruff lint, and formatting check passed after the change.
- PostgreSQL integration checks against the confirmed `fip_test` target passed: classification API/revisions/PIT/review/concurrency (19 tests), and persistent job submission/concurrency/worker (11 tests). They use test fixtures that rebuild schema in this disposable test database.
- A follow-up attempt to rerun mypy and the classification DB tests could not start Python: this shell's venv startup reads a non-ASCII path under ASCII locale and raises `UnicodeDecodeError`. This is an environment startup issue; no result is claimed for that follow-up invocation.
- This five-category sample is a smoke acceptance, not the plan's 30–50 samples per category Golden Dataset or a precision/recall measurement. Positive live confirmation of PASSIVE_INDEX remains unverified because full index membership retrieval was outside the authorized sample scope. Independent human review remains required.
- No business data was written and no commit or push was made.
