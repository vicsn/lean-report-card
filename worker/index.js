import { handleContact } from "./contact.js";
import { handleScore } from "./score.js";
import { json } from "./http.js";

const ROUTES = {
  "/api/contact": handleContact,
  "/api/score": handleScore,
};

export default {
  async fetch(request, env) {
    const handler = ROUTES[new URL(request.url).pathname];
    // Static files under site/ are served before the Worker runs, so anything
    // reaching this point that is not an API route is genuinely unknown.
    if (!handler) return env.ASSETS.fetch(request);
    if (request.method !== "POST") {
      return json({ error: "Use POST." }, 405, { allow: "POST" });
    }
    return handler(request, env);
  },
};
