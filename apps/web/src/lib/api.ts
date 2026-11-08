// Typed client generated from apps/api's OpenAPI schema. Regenerate with `make gen-api`; never hand-edit
// api-schema.ts. Requests go to /api/*, which next.config.ts proxies to FastAPI, so phones need one origin.
import createClient from "openapi-fetch";
import type { components, paths } from "./api-schema";
import { getPostal } from "./postal";
import { userId } from "./user-id";

export const api = createClient<paths>({ baseUrl: "/api" });

// Flyers are local: every request says which postal code the shopper is in (the API has a default when unset).
api.use({
  onRequest({ request }) {
    const postal = getPostal();
    if (postal) request.headers.set("X-Postal-Code", postal);
    return request;
  },
});

/** Pass as `params` on every call: `api.GET("/deals", { params: withUser() })`. */
export const withUser = () => ({ header: { "X-User-Id": userId() } });

export type Schemas = components["schemas"];
