# WhatsApp por QR Code - WAHA local

Execute scripts/Start-Waha.ps1 com o Docker Desktop em modo Linux.
Painel: http://localhost:3000/dashboard/
Credenciais geradas localmente em runtime/waha/.env, ignorado pelo Git.
Usuario: admin. Senha: WAHA_DASHBOARD_PASSWORD. Chave do servidor: WAHA_API_KEY.

O container aura-waha usa apenas a porta de loopback 127.0.0.1:3000.
A sessao fica no volume Docker persistente aura-qr_sessions.
Nao publique o painel via ngrok. Nao compartilhe QR, chave ou sessao.

Esta etapa prepara somente o pareamento. Nenhum webhook ou envio automatico
foi configurado. O WF-02 continua sendo o fluxo separado da API oficial Meta.
A conexao por QR usa integracao nao oficial e pode sofrer desconexao ou bloqueio.

Parar: docker stop aura-waha
Retomar: executar scripts/Start-Waha.ps1 novamente.
Nao excluir o volume de sessoes ao reiniciar.

Referencia: https://waha.devlike.pro/docs/overview/quick-start/
