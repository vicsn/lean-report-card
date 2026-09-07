export async function sendFormEmail(env, { replyTo, subject, text }) {
  if (!env.FORM_FROM || !env.FORM_TO) {
    throw new Error("form_addresses_unconfigured");
  }
  await env.SEND_EMAIL.send({
    from: env.FORM_FROM,
    to: env.FORM_TO,
    replyTo,
    subject,
    text,
  });
}
