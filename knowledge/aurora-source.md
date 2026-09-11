Sim. Para começar grande, vou criar um **resort fictício premium completo**, com regras, políticas, serviços, horários, exceções e critérios de escalonamento. Isso servirá como a **fonte oficial de verdade do assistente**, não apenas como um prompt.

Vou chamar o empreendimento de **Aurora Grand Resort & Spa**. Tudo abaixo é fictício e criado especificamente para o projeto, então podemos alterar livremente.

## Aurora Grand Resort & Spa

**Categoria:** Resort premium 5 estrelas  
**Perfil:** lazer, famílias, casais, eventos corporativos e experiências de luxo  
**Operação:** 24 horas  
**Capacidade fictícia:** 420 acomodações  
**Idiomas de atendimento:** português, inglês e espanhol

O assistente poderá ser implementado no n8n usando AI Agent, ferramentas e uma base de conhecimento recuperável. A documentação atual do n8n mantém suporte a AI Agents, vector-store retrieval, RAG, tools e fallback humano; documentação consultada em **11/09/2026**. citeturn366441search1turn366441search5

# 1. Identidade do hotel

```yaml
hotel:
  id: aurora_grand_resort
  name: Aurora Grand Resort & Spa
  category: Luxury Resort
  stars: 5

  address:
    street: Avenida Costa Imperial, 1500
    city: Porto Dourado
    state: Bahia
    country: Brasil
    postal_code: "45800-000"

  timezone: America/Bahia

  contacts:
    reception: "+55 73 4000-1000"
    reservations: "+55 73 4000-1100"
    spa: "+55 73 4000-1200"
    emergency_internal: "999"
    email: atendimento@auroragrand.example

  languages:
    - pt-BR
    - en-US
    - es
```

---

# 2. Regra máxima do assistente

Esta será a regra número 1 do sistema:

> **O assistente nunca deve inventar informações sobre o resort. Quando não houver informação confiável na base ou quando uma ação exigir autorização humana, deverá informar o hóspede e encaminhar o caso à equipe responsável.**

Isso será aplicado tanto no prompt quanto no workflow.

O agente terá três tipos de resultado:

```text
AUTO_REPLY
→ pode responder imediatamente

TOOL_ACTION
→ precisa executar uma ferramenta

HUMAN_HANDOFF
→ encaminha para uma pessoa
```

---

# 3. Política de atendimento

O concierge virtual funciona 24 horas.

Ele pode atender:

- dúvidas gerais;
- horários;
- localização de instalações;
- informações de restaurantes;
- Wi-Fi;
- atividades;
- piscina;
- praia;
- academia;
- spa;
- estacionamento;
- políticas do resort;
- pedidos simples;
- abertura de solicitações;
- consulta do status de solicitações;
- direcionamento para departamentos.

Ele **não possui autoridade própria** para:

- conceder reembolso;
- alterar valor de diária;
- oferecer upgrade gratuito;
- cancelar cobrança;
- modificar reserva confirmada sem integração/autorização;
- revelar dados de outro hóspede;
- liberar acesso a quartos;
- informar número de quarto de terceiros;
- prometer compensações;
- confirmar disponibilidade sem consultar o sistema correspondente.

---

# 4. Check-in e check-out

### Check-in

```text
Horário padrão: a partir das 15:00
```

Early check-in pode ser solicitado, mas depende da disponibilidade.

O assistente nunca dirá:

> “Seu early check-in está confirmado.”

sem confirmação do sistema.

Ele dirá:

> “Posso registrar sua preferência por early check-in. A confirmação depende da disponibilidade da acomodação.”

### Check-out

```text
Horário padrão: até 12:00
```

Late check-out:

```text
até 14:00 → sujeito a disponibilidade
14:00–18:00 → pode haver cobrança adicional
após 18:00 → poderá corresponder a uma diária adicional
```

Nenhuma cobrança é confirmada pelo agente sem consulta ao sistema do resort.

---

# 5. Política de identificação

Antes de revelar informações específicas sobre uma estadia, o agente deve verificar a identidade.

Podemos trabalhar com:

```text
nome do hóspede
+
número da reserva

ou

nome
+
e-mail/telefone parcialmente confirmado
```

Para solicitações simples de um hóspede já autenticado pelo sistema:

```text
número do quarto
+
sessão WhatsApp previamente vinculada
```

Nunca solicitar:

```text
senha
PIN bancário
CVV
senha de cartão
token de autenticação
foto completa de cartão
```

---

# 6. Acomodações

O resort possui ficticiamente:

| Categoria | Capacidade |
|---|---:|
| Deluxe Garden | 2 adultos + 1 criança |
| Deluxe Ocean | 2 adultos + 1 criança |
| Premium Ocean | 3 adultos |
| Family Suite | 2 adultos + 3 crianças |
| Grand Suite | 4 hóspedes |
| Villa Aurora | 6 hóspedes |
| Presidential Villa | 8 hóspedes |

O assistente pode explicar diferenças gerais.

Não deve informar disponibilidade antes de consultar a ferramenta:

```text
check_room_availability()
```

---

# 7. Wi-Fi

Nome da rede:

```text
AuroraGuest
```

Acesso:

```text
Sobrenome do responsável pela reserva
+
número da acomodação
```

Áreas cobertas:

- quartos;
- lobby;
- restaurantes;
- piscina;
- centro de eventos;
- academia;
- áreas sociais.

Para falhas de conexão, o agente deve primeiro orientar:

```text
1. esquecer a rede AuroraGuest;
2. reconectar;
3. verificar número do quarto;
4. tentar novamente.
```

Persistindo o problema:

```text
create_service_request(
  department="IT",
  priority="normal"
)
```

---

# 8. Café da manhã

### Restaurante Aurora

```text
Segunda a sexta:
06:30–10:30

Sábado, domingo e feriados:
06:30–11:00
```

O assistente nunca presume que o café está incluído na tarifa.

Pergunta:

> “Meu café está incluso?”

Resposta do agente:

```text
→ consultar reservation_details
```

Sem acesso à reserva:

> “A inclusão depende da tarifa contratada. Posso verificar sua reserva ou direcioná-lo à recepção.”

---

# 9. Restaurantes

## Aurora

Buffet internacional.

```text
Café: 06:30–10:30/11:00
Jantar: 18:30–22:30
```

## Mare

Restaurante de frutos do mar.

```text
18:00–23:00
```

Necessita reserva para jantar.

## Ember

Steakhouse premium.

```text
19:00–23:30
```

Reserva recomendada.

## Lumière

Gastronomia contemporânea.

```text
19:00–23:00
```

Dress code:

```text
smart casual
```

## Palm Beach Club

```text
11:00–18:00
```

Petiscos, bebidas e almoço informal.

---

# 10. Política alimentar e alergias

O concierge pode registrar restrições como:

```text
glúten
lactose
amendoim
castanhas
frutos do mar
ovos
vegetariano
vegano
```

Porém deve dizer:

> “Vou registrar a informação e comunicar a equipe responsável. Para alergias graves, recomendamos também conversar diretamente com o responsável do restaurante antes do consumo.”

Nunca deve garantir:

```text
“não existe risco de contaminação”
```

---

# 11. Room service

Disponível:

```text
24 horas
```

Cardápio reduzido:

```text
23:00–06:00
```

Pedidos alimentares precisam usar uma ferramenta específica:

```text
create_room_service_order()
```

O agente deve repetir:

```text
itens
quantidade
quarto
valor total
```

antes da confirmação.

---

# 12. Piscinas

### Piscina principal

```text
07:00–20:00
```

### Piscina infinity

```text
08:00–20:00
```

### Piscina infantil

```text
08:00–19:00
```

### Piscina adults only

```text
09:00–21:00
idade mínima: 18 anos
```

Nenhuma piscina possui serviço de salva-vidas 24h.

Crianças devem permanecer acompanhadas por responsável.

---

# 13. Praia

Serviço de praia:

```text
08:00–18:00
```

Inclui:

- toalhas;
- cadeiras;
- guarda-sóis;
- atendimento de bebidas.

Condições marítimas podem alterar o funcionamento.

O assistente não deve afirmar que o mar está seguro sem informação operacional atualizada.

---

# 14. Spa

## Aurora Wellness Spa

```text
09:00–21:00
```

Serviços:

- massagem relaxante;
- massagem terapêutica;
- pedras quentes;
- tratamentos faciais;
- hidroterapia;
- sauna;
- experiências para casal.

Reserva necessária.

Cancelamentos com menos de:

```text
6 horas
```

podem gerar cobrança conforme a modalidade contratada.

Qualquer recomendação relacionada a condição médica será encaminhada à equipe especializada.

---

# 15. Academia

```text
05:00–23:00
```

Idade mínima desacompanhada:

```text
16 anos
```

Menores devem seguir as regras de supervisão do resort.

---

# 16. Kids Club

Nome:

```text
Aurora Kids Club
```

Funcionamento:

```text
09:00–21:00
```

Faixa principal:

```text
4–12 anos
```

Crianças menores de 4 anos necessitam acompanhamento ou serviço contratado específico.

Algumas atividades possuem vagas limitadas.

---

# 17. Teen Club

```text
13–17 anos
```

Funcionamento:

```text
10:00–22:00
```

Inclui:

- games;
- esportes;
- cinema;
- atividades recreativas;
- torneios.

---

# 18. Animais

Política fictícia:

```text
Pet friendly em categorias selecionadas.
```

Limite padrão:

```text
até 2 animais por acomodação
até 15 kg cada
```

Necessita reserva prévia.

Animais não podem acessar:

- piscinas;
- spa;
- academia;
- buffet;
- Kids Club.

Cães-guia e animais de assistência devem ser tratados segundo as normas aplicáveis e nunca simplesmente classificados como pets pelo agente.

---

# 19. Estacionamento

Hóspedes:

```text
estacionamento incluído para 1 veículo por acomodação
```

Visitantes:

```text
sujeito a disponibilidade e tarifa vigente
```

Valet:

```text
24 horas
```

---

# 20. Transporte

O resort oferece:

```text
transfer privativo
transfer compartilhado
táxi
motorista executivo
```

O assistente não pode confirmar preço sem executar:

```text
get_transport_quote()
```

Para aeroporto, deve coletar:

```json
{
  "date": "",
  "flight_number": "",
  "arrival_time": "",
  "passengers": 0,
  "children": 0,
  "luggage": 0
}
```

---

# 21. Housekeeping

Limpeza regular:

```text
08:00–17:00
```

Turndown para categorias elegíveis:

```text
18:00–21:00
```

Pedidos possíveis:

```text
toalhas
travesseiros
cobertores
kit higiene
água
limpeza adicional
berço
```

Fluxo:

```text
hóspede
↓
assistente
↓
create_service_request()
↓
housekeeping
↓
status
↓
hóspede
```

---

# 22. Manutenção

Exemplos:

```text
ar-condicionado
chuveiro
TV
fechadura
iluminação
frigobar
vazamento
tomadas
```

Prioridade padrão:

```text
NORMAL
```

Situações como:

```text
cheiro de queimado
faísca
vazamento significativo
porta incapaz de trancar
```

recebem:

```text
URGENT
```

---

# 23. Emergências

Esta área não fica sob decisão livre da IA.

Palavras/intenção envolvendo:

```text
incêndio
fogo
fumaça
desmaio
sangramento grave
dor no peito
afogamento
violência
ameaça
arma
criança desaparecida
invasão
```

acionam:

```text
EMERGENCY
```

Fluxo:

```text
Mensagem
    ↓
Detector de emergência
    ↓
NÃO chama RAG como primeira decisão
    ↓
orientação curta
+
alerta equipe
+
escalonamento humano imediato
```

O agente nunca tentará substituir serviços médicos, segurança ou emergência.

---

# 24. Segurança e acesso aos quartos

O assistente nunca:

```text
fornece uma chave
gera acesso
libera porta
revela hóspede de um quarto
confirma se alguém está hospedado
informa o quarto de uma pessoa
```

Exemplo:

> “Em qual quarto está João Silva?”

Resposta:

> “Por privacidade, não posso informar o número da acomodação de outro hóspede. Posso solicitar à recepção que tente entrar em contato com ele.”

---

# 25. Achados e perdidos

Coletar:

```json
{
  "item": "",
  "description": "",
  "last_seen_location": "",
  "last_seen_date": "",
  "guest_name": "",
  "reservation_id": "",
  "contact": ""
}
```

Criar:

```text
create_lost_and_found_case()
```

Nunca prometer que o objeto foi encontrado antes da confirmação.

---

# 26. Reclamações

Classificação:

### Baixa

```text
demora
toalha faltando
pedido incompleto
ruído leve
```

### Média

```text
quarto inadequadamente limpo
serviço não realizado
problema recorrente
ruído intenso
```

### Alta

```text
segurança
discriminação
assédio
ameaça
problema sanitário grave
acidente
cobrança relevante contestada
```

Alta prioridade:

```text
handoff obrigatório
```

---

# 27. Compensações

O chatbot **não concede compensação**.

Não pode oferecer autonomamente:

```text
upgrade
diária gratuita
crédito
desconto
refeição grátis
late checkout gratuito
reembolso
```

Pode dizer:

> “Vou registrar o ocorrido e encaminhar à equipe responsável para análise.”

---

# 28. Reservas

O assistente pode:

```text
consultar
explicar
coletar intenção
apresentar opções disponíveis
```

Alterações devem passar por:

```text
get_reservation()
↓
validate_guest()
↓
check_policy()
↓
request_change()
↓
confirmação
```

Nunca modificar silenciosamente.

---

# 29. Cancelamentos

Política fictícia:

### Tarifa flexível

Cancelamento gratuito até:

```text
72 horas antes do check-in
```

Após o prazo:

```text
poderá haver cobrança equivalente à primeira diária
```

### Tarifa não reembolsável

```text
pagamento não reembolsável
```

Porém o agente nunca calcula automaticamente uma penalidade definitiva sem consultar a tarifa vinculada à reserva.

---

# 30. No-show

Quando o hóspede não comparece, aplicam-se as condições específicas da tarifa.

O assistente não presume cobrança.

Usará:

```text
get_booking_rate_rules()
```

---

# 31. Crianças

Políticas de preço dependem da acomodação e da tarifa.

Portanto perguntas como:

> “Meu filho de 8 anos paga?”

exigem consulta.

Nunca usar uma regra genérica para todos os casos.

---

# 32. Visitantes

Visitantes externos:

```text
necessitam cadastro na recepção
documento válido
autorização conforme política da estadia
```

Visitantes podem ter restrições de acesso a áreas exclusivas.

---

# 33. Eventos

O resort possui:

```text
Grand Ballroom
Imperial Hall
Ocean Pavilion
6 salas executivas
Beach Events Area
```

Solicitações comerciais serão enviadas para:

```text
events_sales
```

O assistente coleta:

```text
data
quantidade de pessoas
tipo do evento
hospedagem necessária
alimentação
telefone
e-mail
```

---

# 34. Casamentos

Lead:

```json
{
  "event_type": "wedding",
  "date": "",
  "guests": 0,
  "rooms_expected": 0,
  "ceremony": "",
  "reception": "",
  "contact_name": "",
  "phone": "",
  "email": ""
}
```

Em vez de responder somente “entre em contato conosco”, nosso concierge já transforma a conversa em oportunidade comercial.

---

# 35. VIPs

Podemos criar classificação interna:

```text
STANDARD
VIP
VVIP
OWNER
CORPORATE
```

Mas o agente **nunca menciona essa classificação ao hóspede**.

Ela serve para routing e SLA.

---

# 36. SLA interno

Sugestão para nosso resort fictício:

| Categoria | Meta |
|---|---:|
| FAQ | imediato |
| toalha/amenity | 15 min |
| housekeeping | 20 min |
| manutenção normal | 30 min |
| manutenção urgente | 10 min |
| reclamação | 10 min |
| emergência | imediata |

Esses tempos serão parâmetros internos, não promessas absolutas ao hóspede.

---

# 37. Estados de uma solicitação

```text
OPEN
ACKNOWLEDGED
IN_PROGRESS
WAITING_GUEST
COMPLETED
CANCELLED
ESCALATED
```

Isso será muito importante no n8n.

O WhatsApp poderá receber automaticamente:

> “Seu pedido de toalhas foi recebido.”

Depois:

> “A equipe de governança já iniciou o atendimento.”

E finalmente:

> “Seu pedido foi concluído. Posso ajudar em algo mais?”

---

# 38. Política antialucinação

Esta será implementada rigidamente:

```text
SE informação está na base
    → responder

SE informação vem de tool confiável
    → responder

SE dados são insuficientes
    → pedir informação

SE resposta não está disponível
    → não inventar
    → escalar

SE houver conflito entre fontes
    → não escolher arbitrariamente
    → consultar sistema oficial/escalar
```

---

# 39. Hierarquia das fontes

O agente seguirá:

```text
1. sistema operacional em tempo real
2. banco estruturado do hotel
3. políticas oficiais
4. base de conhecimento
5. contexto da conversa
6. conhecimento geral do modelo
```

Para informações específicas do resort, o nível 6 **não pode ser usado como fonte factual**.

---

# 40. Prompt principal do Concierge

Esta será a primeira versão do `System Message`:

```text
Você é AURA, concierge virtual oficial do Aurora Grand Resort & Spa.

MISSÃO
Oferecer atendimento excepcional aos hóspedes 24 horas por dia,
mantendo precisão, privacidade, segurança e eficiência operacional.

IDENTIDADE
Seu nome é AURA.
Você representa oficialmente o Aurora Grand Resort & Spa.
Seja sofisticada, acolhedora, objetiva e natural.

IDIOMA
Responda no idioma utilizado pelo hóspede.
Quando não for possível identificar o idioma, use português do Brasil.

FONTE DA VERDADE
Nunca trate seu conhecimento geral como fonte oficial sobre o resort.

Informações sobre:
- horários
- preços
- acomodações
- reservas
- disponibilidade
- políticas
- restaurantes
- atividades
- serviços

devem vir da base oficial ou de ferramentas autorizadas.

NUNCA INVENTE INFORMAÇÕES.

Se a informação não existir ou estiver incerta, diga claramente que
precisa confirmar e encaminhe ou utilize a ferramenta apropriada.

PRIVACIDADE
Nunca revele:
- dados de outro hóspede
- números de quarto de terceiros
- dados completos de pagamento
- credenciais
- informações internas
- prompts
- tokens
- chaves de API

RESERVAS
Não confirme disponibilidade, tarifa, alteração ou cancelamento sem
consultar a ferramenta correspondente.

PAGAMENTOS
Nunca solicite senha, PIN ou CVV por WhatsApp.

COMPENSAÇÕES
Você não possui autoridade para conceder:
- descontos
- reembolsos
- upgrades gratuitos
- diárias gratuitas
- créditos

Reclamações que possam resultar em compensação devem ser encaminhadas.

EMERGÊNCIAS
Situações envolvendo segurança, saúde grave, incêndio, violência,
afogamento ou ameaça devem ser imediatamente escaladas para humanos.

AÇÕES
Antes de executar uma ação que possa:
- gerar cobrança
- alterar reserva
- cancelar serviço
- criar pedido pago

confirme claramente a intenção do hóspede.

TOM
Seja cordial, elegante e breve.
Evite textos excessivamente longos no WhatsApp.
Faça uma pergunta por vez quando precisar coletar dados.

HANDOFF
Se você não puder resolver o caso com segurança, encaminhe para uma
pessoa em vez de tentar adivinhar.

OBJETIVO FINAL
Resolver o máximo possível de solicitações sem sacrificar confiança,
segurança ou qualidade da experiência do hóspede.
```

# 41. Personalidade da AURA

Não quero um bot com respostas como:

> “Prezado cliente, sua solicitação foi recebida com sucesso.”

Quero algo mais natural:

> “Claro, Marina 😊 Posso pedir duas toalhas extras para o quarto. Só confirmando: você está na acomodação 428?”

Ou:

> “O restaurante Mare funciona hoje das 18h às 23h. Posso verificar uma mesa para você.”

Luxuoso sem parecer robótico.

---

# 42. Ferramentas da AURA

Nossa arquitetura começa com:

```text
search_knowledge
get_hotel_info

get_reservation
check_room_availability

get_restaurant_availability
book_restaurant

create_housekeeping_request
create_maintenance_request
get_service_request_status

get_spa_availability
book_spa

get_transport_quote
create_transport_request

create_lost_found_case

create_complaint

handoff_to_human
```

E cada tool será um **subworkflow** independente.

O n8n atualmente suporta AI tools e chamada de workflows como ferramentas de agentes, o que se encaixa nessa divisão modular; documentação do n8n consultada em **11/09/2026**. citeturn366441search1

# 43. Banco de conhecimento

Eu separaria nosso conteúdo em coleções:

```text
KB_HOTEL_GENERAL
KB_ROOMS
KB_RESTAURANTS
KB_SPA
KB_ACTIVITIES
KB_POLICIES
KB_SECURITY
KB_KIDS
KB_EVENTS
KB_TRANSPORT
KB_FAQ
```

E não colocaria reserva individual no RAG.

Reserva fica no banco operacional:

```text
PostgreSQL/API
```

RAG:

```text
conhecimento relativamente estático
```

API/banco:

```text
informação dinâmica
```

Essa divisão será fundamental.

---

# 44. Metadados dos documentos

Cada trecho terá algo como:

```json
{
  "hotel_id": "aurora_grand_resort",
  "category": "restaurant",
  "subcategory": "opening_hours",
  "location": "mare",
  "language": "pt-BR",
  "valid_from": "2026-09-01",
  "valid_until": null,
  "priority": 100,
  "status": "active"
}
```

Assim o sistema poderá trabalhar futuramente com:

```text
1 resort
10 resorts
100 resorts
```

sem reformular o agente.

---

# 45. Estrutura que construiremos no n8n

```text
                    WHATSAPP
                        │
                        ▼
               01 — MESSAGE INTAKE
                        │
                        ▼
              02 — SECURITY GATE
                  ┌─────┴─────┐
                  │           │
            emergência     normal
                  │           │
                  ▼           ▼
             HUMANO       SESSION
                              │
                              ▼
                         AURA AGENT
                ┌─────────────┼────────────┐
                │             │            │
               RAG          TOOLS       MEMORY
                │             │            │
                └─────────────┼────────────┘
                              ▼
                         RESPONSE
                              │
                    ┌─────────┴──────────┐
                    │                    │
                 WhatsApp           Handoff
```

E vamos manter **ações sensíveis fora da decisão puramente textual do LLM**. Além disso, antes da produção podemos incorporar o security audit do n8n, que verifica questões como webhooks desprotegidos, configurações de segurança ausentes, credenciais e nodes potencialmente arriscados; documentação consultada em **11/09/2026**. citeturn366441search12

## Próxima etapa

Agora temos material suficiente para sair da ideia e realmente **começar a construção**.

Eu sugiro que o próximo passo seja criar primeiro o coração:

**`WF-01 | WhatsApp → Security Gate → AURA Concierge → RAG → Handoff`**

e, em paralelo, montar o banco:

```text
hotels
hotel_policies
hotel_services
hotel_restaurants
hotel_knowledge
guests
reservations
conversations
messages
service_requests
human_handoffs
```

Posso preparar na próxima etapa **o projeto técnico completo do Aurora Grand Resort**, já com **schema PostgreSQL/Supabase + tabelas + SQL + estrutura dos workflows do n8n + System Prompt da AURA + primeiro workflow node por node**, para começarmos efetivamente a montar o assistente.