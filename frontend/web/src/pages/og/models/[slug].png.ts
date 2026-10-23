import type { APIRoute } from "astro";

import { internalGet, isNotFound } from "../../../lib/api";
import { modelCard } from "../../../lib/og/cards";
import { ogResponse } from "../../../lib/og/render";
import type { ModelDetail } from "../../../lib/types";

// /models/{slug} 和 /free/{slug} 共用
export const GET: APIRoute = async ({ params }) => {
  try {
    const model = await internalGet<ModelDetail>(
      `/models/${encodeURIComponent(params.slug ?? "")}`,
    );
    return await ogResponse(modelCard(model));
  } catch (err) {
    if (isNotFound(err)) return new Response(null, { status: 404 });
    throw err;
  }
};
