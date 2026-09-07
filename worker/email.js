export async function sendFormEmail(env, { replyTo, subject, text }) {
  await env.SEND_EMAIL.send({
    from: env.FORM_FROM,
    to: env.FORM_TO,
    replyTo,
    subject,
    text,
  });
}
