const MAX_URL = 2048;
const MAX_EMAIL = 320;

function json(body, status) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

function repositoryError(value) {
  if (!value || value.length > MAX_URL) return "Send an http or https repository URL.";
  let parsed;
  try {
    parsed = new URL(value);
  } catch {
    return "Send a well-formed http or https URL.";
  }
  if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
    return "Only http and https URLs are accepted.";
  }
  if (!parsed.hostname) return "The URL must include a host.";
  if (parsed.username || parsed.password) {
    return "Repository URLs may not contain credentials.";
  }
  return "";
}

export async function onRequestPost({ request, env }) {
  let payload;
  try {
    payload = await request.json();
  } catch {
    return json({ error: "Send a JSON body." }, 400);
  }
  const repository = String(payload.repository || "").trim();
  const slug = String(payload.repository_slug || "").trim();
  const email = String(payload.email || "").trim();
  const rescan = payload.rescan === true;
  const publish = payload.publish === true;
  const invalid = repositoryError(repository);
  if (invalid) return json({ error: invalid }, 400);
  if (!email.includes("@") || email.length > MAX_EMAIL) {
    return json({ error: "Enter a valid contact email." }, 400);
  }
  const lines = [
    `Repository: ${repository}`,
    `Slug: ${slug || "unknown"}`,
    `Contact: ${email}`,
    `Rescan: ${rescan ? "yes" : "no"}`,
    `Publish: ${publish ? "yes" : "no"}`,
  ];
  try {
    await env.SEND_EMAIL.send({
      from: env.FORM_FROM,
      to: env.FORM_TO,
      replyTo: email,
      subject: `Score request: ${slug || repository}`,
      text: `${lines.join("\n")}\n`,
    });
  } catch (error) {
    console.error("score delivery failed", error?.code || error);
    return json({ error: "The submission could not be delivered. Try again later." }, 502);
  }
  return json({ status: "queued" }, 202);
}
