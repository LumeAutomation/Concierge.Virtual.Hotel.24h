# Modelo comercial AURA para hotéis e resorts

## O que está pronto

A instalação demonstra a jornada de um hotel fictício: identidade visual própria, catálogo de acomodações e planos, políticas locais, reservas, boas-vindas pelo WhatsApp, pré-check-in, pedidos, atendimento humano e checkout controlado pela equipe. Não depende de API de IA paga.

Em **Meu hotel** (`/hotel`), administradores e gestores podem configurar nome, assistente, apresentação, cor, endereço, contatos e quantidade de acomodações. As próximas mensagens usam a identidade configurada; atualize outras páginas abertas para carregar a marca. Políticas e regras são editadas em **Políticas**, com rascunho e publicação separados.

O Hotel Aura é fictício. Endereço, domínio `.example`, serviços, horários e valores são dados de demonstração. Não há telefone público real configurado no modelo. Nenhuma conexão WAHA é alterada ao mudar os dados da identidade.

## Catálogo demonstrativo

- 420 acomodações, cinco categorias: Aura Superior, Aura Jardim, Aura Família, Suíte Horizonte e Villa Serenidade.
- Restaurante Brisa, Restaurante Terra, Bar Horizonte e room service com cardápio de referência.
- Piscinas, academia, Aura Wellness Spa, Kids Club e Teen Club.
- Planos Aura Essencial, Aura Sabores e Aura Inclusive, com exclusões explícitas.
- Estacionamento, pet, lavanderia, minibar e traslado fictício com preços de referência.
- 101 políticas base, incluindo regras internas de limites e encaminhamento.

Inventário, reservas, pagamentos, disponibilidade e execução de serviços não são confirmados apenas porque aparecem no catálogo. Informações já publicadas pela equipe em uma instalação prevalecem sobre o catálogo base; esta evolução não sobrescreve essas publicações.

## Exportar para o próximo cliente

Em **Meu hotel**, use **Baixar modelo do hotel**. O JSON contém identidade e políticas vigentes, inclusive as internas, para uso da equipe de implantação. Não inclui rascunhos não publicados, reservas, hóspedes, conversas, protocolos, usuários, senhas, chaves, sessões WhatsApp ou bancos n8n.

Em uma cópia nova do código, importe para um banco ainda inexistente:

```powershell
python scripts/import_hotel_template.py --template "C:\Implantacao\modelo-hotel.json" --database "C:\Instalacoes\HotelCliente\runtime\aura.sqlite3"
```

Esse comando prepara o banco, não instala nem inicia serviços. A configuração importada é salva e as políticas entram como **rascunhos**, aguardando revisão e publicação. Em modo Demonstração, o catálogo demonstrativo base continua disponível. Em Produção, somente revisões publicadas e validadas para produção podem responder; o modelo importado como rascunho não recebe essa validação. Consulte docs/production-mode.md. A importação recusa arquivo de banco existente e valida o pacote antes de criar o destino.

## Uma instalação independente por hotel

O isolamento comercial atual é por instalação, não por um seletor de clientes dentro do mesmo banco. Cada hotel precisa de:

1. Diretório/cópia de aplicação e banco SQLite próprios. Não copiar `runtime`, `Acessos`, `.env`, sessões, backups operacionais, cookies ou o arquivo de acesso inicial de outro hotel.
2. Usuários individuais e senha inicial nova, criada pelo fluxo de configuração de acessos.
3. WAHA e n8n próprios, credenciais exclusivas, volume Docker e pareamento do WhatsApp do cliente. Exportar a identidade não exporta esse pareamento.
4. Configuração dos endpoints, portas, tarefas de inicialização, logs e backups para essa instalação. Os scripts legados usam portas e tarefas padrão; não os executar para dois hotéis na mesma máquina sem adaptação e validação dessas referências.
5. Revisão do catálogo pelo responsável do hotel, incluindo capacidade, horários, inclusões, valores, regras e contatos. Remover ou substituir dados fictícios antes da operação real.
6. Teste de ponta a ponta com contatos autorizados e execução conferida pela equipe.

A configuração `AURA_DB` seleciona o banco na execução da aplicação. Ela sozinha não isola WAHA, n8n, supervisor, backups ou outros serviços. Para o primeiro cliente, a rota mais simples é uma máquina/ambiente dedicado. Não há, nesta entrega, hospedagem pública, painel central multiempresa, gestão de assinaturas, integração PMS ou isolamento SaaS em banco compartilhado.

## Roteiro de apresentação

Use exclusivamente dados fictícios e contato de demonstração autorizado. Abra Meu hotel para apresentar identidade e catálogo. Crie uma reserva fictícia, envie boas-vindas pelo botão, realize o pré-check-in e registre o check-in após a conferência de demonstração. Faça um pedido de duas toalhas, assuma o atendimento, mostre o histórico e a pausa da Hostess. Conclua o pedido e confirme o recebimento pelo contato de demonstração. Finalize com a revisão de pendências e checkout. Os testes automatizados não enviam essas mensagens reais.

## Validação

`python -m unittest discover -s tests`

`python scripts/check_hotel_profile_browser.py`

O teste de navegador usa banco temporário, verifica permissões, mudança de identidade, exportação e tamanho de tela móvel. Não envia WhatsApp real.
