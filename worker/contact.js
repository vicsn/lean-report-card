import { sendFormEmail } from "./email.js";
import { json } from "./http.js";

const MAX_MESSAGE = 4000;
const MAX_EMAIL = 320;

export async function handleContact(request, env) {
  let payload;
  try {
    payload = await request.json();
  } catch {
    return json({ error: "Send a JSON body." }, 400);
  }
  const email = String(payload.email || "").trim();
  const message = String(payload.message || "").trim();
  if (!email.includes("@") || email.length > MAX_EMAIL) {
    return json({ error: "Enter a valid contact email." }, 400);
  }
  if (!message || message.length > MAX_MESSAGE) {
    return json({ error: `Enter a message of up to ${MAX_MESSAGE} characters.` }, 400);
  }
  try {
    await sendFormEmail(env, {
      replyTo: email,
      subject: `Contact form: ${email}`,
      text: `From: ${email}\n\n${message}\n`,
    });
  } catch (error) {
    console.error("contact delivery failed", error?.message || error);
    return json({ error: "The message could not be delivered. Try again later." }, 502);
  }
  return json({ status: "received" }, 202);
}
