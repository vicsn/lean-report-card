const API_BASE = "https://api.cloudflare.com/client/v4/accounts";

// Pages Functions cannot use the Workers `send_email` binding, so submissions
// go out through the Email Service REST API instead.
export async function sendFormEmail(env, { replyTo, subject, text }) {
  if (!env.CF_ACCOUNT_ID || !env.CF_EMAIL_TOKEN) {
    throw new Error("email_transport_unconfigured");
  }
  const response = await fetch(`${API_BASE}/${env.CF_ACCOUNT_ID}/email/sending/send`, {
    method: "POST",
    headers: {
      authorization: `Bearer ${env.CF_EMAIL_TOKEN}`,
      "content-type": "application/json",
    },
    body: JSON.stringify({
      from: env.FORM_FROM,
      to: env.FORM_TO,
      reply_to: replyTo,
      subject,
      text,
    }),
  });
  const body = await response.json().catch(() => null);
  if (!response.ok || body?.success !== true) {
    throw new Error(body?.errors?.[0]?.message || `http_${response.status}`);
  }
}
