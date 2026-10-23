import type { APIRoute } from "astro";

import { DEFAULT_CARD } from "../../lib/og/cards";
import { ogResponse } from "../../lib/og/render";

export const GET: APIRoute = () => ogResponse(DEFAULT_CARD);
