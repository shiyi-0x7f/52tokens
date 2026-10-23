import type { APIRoute } from "astro";

import { internalGet, isNotFound } from "../../../lib/api";
import { dealCard } from "../../../lib/og/cards";
import { ogResponse } from "../../../lib/og/render";
import type { Deal } from "../../../lib/types";

export const GET: APIRoute = async ({ params }) => {
  try {
    const deal = await internalGet<Deal>(`/deals/${encodeURIComponent(params.slug ?? "")}`);
    return await ogResponse(dealCard(deal));
  } catch (err) {
    if (isNotFound(err)) return new Response(null, { status: 404 });
    throw err;
  }
};
