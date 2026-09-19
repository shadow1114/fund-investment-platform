import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";

import {
  fundListEnvelope,
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
  http.get("/api/v1/session", () => HttpResponse.json(sessionEnvelope)),
  http.get("/api/v1/operations/:operationId", () =>
    HttpResponse.json(operationEnvelope),
  ),
  http.get("/api/v1/funds", () => HttpResponse.json(fundListEnvelope)),
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
