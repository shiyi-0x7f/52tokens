import type { APIRoute } from "astro";

import { internalGet, isNotFound } from "../../../lib/api";
import { platformCard } from "../../../lib/og/cards";
import { ogResponse } from "../../../lib/og/render";
import type { Deal, Platform } from "../../../lib/types";

export const GET: APIRoute = async ({ params }) => {
  try {
    const platform = await internalGet<Platform>(
      `/platforms/${encodeURIComponent(params.slug ?? "")}`,
    );
    const deals = await internalGet<Deal[]>("/deals", { platform: platform.slug, limit: 20 });
    return await ogResponse(platformCard(platform, deals));
  } catch (err) {
    if (isNotFound(err)) return new Response(null, { status: 404 });
    throw err;
  }
};
