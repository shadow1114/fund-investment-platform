import {
  classificationCatalog,
  emptyClassificationHistory,
} from "./classificationFixtures";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";

import {
  fundDetailEnvelope,
  fundEvaluationEnvelope,
  fundListEnvelope,
  fundIngestionListEnvelope,
  fundIngestionSubmissionEnvelope,
  fundBasicInfoHistoryEnvelope,
  fundNavEnvelope,
  fundScoreEnvelope,
  operationEnvelope,
  portfolioEnvelope,
  portfolioListEnvelope,
  sessionEnvelope,
  universeDetailEnvelope,
  universeListEnvelope,
} from "./contractFixtures";

export const requestLog: URL[] = [];

export const resetRequestLog = () => {
  requestLog.length = 0;
};

export const contractHandlers = [
  http.get("/api/v1/fund-classifications/catalog", () =>
    HttpResponse.json(classificationCatalog),
  ),
  http.get("/api/v1/funds/:fundId/classification-history", () =>
    HttpResponse.json(emptyClassificationHistory),
  ),
  http.get("/api/v1/funds/:fundId/ingestions", () =>
    HttpResponse.json(fundIngestionListEnvelope),
  ),
  http.post("/api/v1/funds/:fundId/ingestions", () =>
    HttpResponse.json(fundIngestionSubmissionEnvelope, { status: 202 }),
  ),
  http.post("/api/v1/fund-ingestions", () =>
    HttpResponse.json(fundIngestionSubmissionEnvelope, { status: 202 }),
  ),
  http.get("/api/v1/funds/:fundId/basic-info-history", () =>
    HttpResponse.json(fundBasicInfoHistoryEnvelope),
  ),
  http.get("/api/v1/session", () => HttpResponse.json(sessionEnvelope)),
  http.get("/api/v1/operations/:operationId", () =>
    HttpResponse.json(operationEnvelope),
  ),
  http.get("/api/v1/funds", () => HttpResponse.json(fundListEnvelope)),
  http.get("/api/v1/funds/:fundId", () =>
    HttpResponse.json(fundDetailEnvelope),
  ),
  http.get("/api/v1/funds/:fundId/nav-series", () =>
    HttpResponse.json(fundNavEnvelope),
  ),
  http.get("/api/v1/funds/:fundId/evaluations", () =>
    HttpResponse.json(fundEvaluationEnvelope),
  ),
  http.get("/api/v1/funds/:fundId/scores", () =>
    HttpResponse.json(fundScoreEnvelope),
  ),
  http.get("/api/v1/fund-universes", () =>
    HttpResponse.json(universeListEnvelope),
  ),
  http.get("/api/v1/fund-universes/:universeId", () =>
    HttpResponse.json(universeDetailEnvelope),
  ),
  http.get("/api/v1/portfolios", () =>
    HttpResponse.json(portfolioListEnvelope),
  ),
  http.get("/api/v1/portfolios/:portfolioId", () =>
    HttpResponse.json(portfolioEnvelope),
  ),
];

export const server = setupServer(...contractHandlers);

server.events.on("request:start", ({ request }) => {
  requestLog.push(new URL(request.url));
});
