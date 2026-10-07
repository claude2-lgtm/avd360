/**
 * AVD 360° — envio de e-mails pela conta Google que implantar este script.
 *
 * Como usar:
 * 1. Entre em https://script.google.com com a conta remetente (gp@grupogestao.co).
 * 2. Novo projeto → apague o conteúdo e cole este arquivo.
 * 3. Troque COLE_AQUI_O_SEGREDO pelo mesmo valor de APPS_SCRIPT_SECRET no Render.
 * 4. Implantar → Nova implantação → tipo "App da Web"
 *      Executar como: Eu
 *      Quem pode acessar: Qualquer pessoa
 * 5. Autorize o acesso e copie a URL do app da Web para APPS_SCRIPT_URL no Render.
 */
const SECRET = 'COLE_AQUI_O_SEGREDO';

function doPost(e) {
  try {
    const data = JSON.parse(e.postData.contents);
    if (data.secret !== SECRET) {
      return reply({ ok: false, error: 'segredo inválido' });
    }
    const attachments = (data.attachments || []).map(function (a) {
      return Utilities.newBlob(Utilities.base64Decode(a.content), a.mimeType || 'application/pdf', a.name);
    });
    MailApp.sendEmail({
      to: data.to,
      subject: data.subject,
      htmlBody: data.htmlBody,
      name: data.name || 'AVD 360°',
      attachments: attachments,
    });
    return reply({ ok: true, remaining: MailApp.getRemainingDailyQuota() });
  } catch (err) {
    return reply({ ok: false, error: String(err) });
  }
}

function reply(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
}
