"""Small bilingual presentation layer over existing interaction/reservation state."""
import json
import re
from datetime import datetime, timezone
import knowledge_engine as knowledge
import hotel_profile


def key(text):
    return knowledge.question_key(text)


def response(text, **extra):
    return dict(route='AUTO_REPLY', reply=text, policy_ids=[], ai_used=False,
                answer_mode='conversation', **extra)


# Labels are presentation; commands still pass through existing service handlers.
MENUS = {
 'wifi': ('📶', [('Senha', 'Password', 'senha do wifi'), ('Conectar', 'Connect', 'como conectar wifi'), ('Problema no Wi-Fi', 'Wi-Fi problem', 'wifi nao funciona')]),
 'cafe': ('☕', [('Horário', 'Hours', 'horario cafe da manha'), ('Local', 'Location', 'local cafe da manha'), ('Cardápio', 'Menu', 'cardapio cafe da manha')]),
 'piscina': ('🏊', [('Horário', 'Hours', 'horario piscina'), ('Localização', 'Location', 'localizacao piscina'), ('Regras', 'Rules', 'regras piscina')]),
 'quarto': ('🛏️', [('Limpeza', 'Cleaning', 'quero limpeza'), ('Toalhas', 'Towels', 'quero toalhas'), ('Manutenção', 'Maintenance', 'preciso manutencao'), ('Outra coisa', 'Something else', 'outro assunto quarto')]),
 'checkin': ('🧳', [('Horário', 'Hours', 'horario check in'), ('Pré-check-in', 'Pre-check-in', 'pre-check-in'), ('Minha reserva', 'My booking', 'minha reserva')]),
 'checkout': ('🧳', [('Horário', 'Hours', 'horario check out'), ('Solicitar saída', 'Request checkout', 'quero checkout')]),
 'senha': ('🔑', [('Wi-Fi', 'Wi-Fi', 'senha do wifi'), ('Outra senha', 'Another password', 'senha pessoal')]),
 'restaurante': ('🍽️', [('Horário', 'Hours', 'horario restaurante'), ('Cardápio', 'Menu', 'cardapio restaurante'), ('Reserva de mesa', 'Book a table', 'reservar mesa')]),
}
TOPICS = {'wi fi':'wifi','wifi':'wifi','internet':'wifi','cafe':'cafe','cafe da manha':'cafe','breakfast':'cafe',
          'piscina':'piscina','pool':'piscina','quarto':'quarto','room':'quarto','check in':'checkin','checkin':'checkin',
          'check out':'checkout','checkout':'checkout','senha':'senha','password':'senha','restaurante':'restaurante','restaurant':'restaurante'}
YES = {'1','sim','yes','agora','now','pode','quero','yes please','sure'}
NO = {'2','nao','no','depois','later','not now','agora nao','amanha','tomorrow'}


def recent(db, session):
    row=db.execute('SELECT response,created_at FROM interactions WHERE session_id=? ORDER BY created_at DESC,rowid DESC LIMIT 1',(session,)).fetchone()
    if not row:return {}
    if (datetime.now(timezone.utc)-datetime.fromisoformat(row[1])).total_seconds()>1800:return {}
    return json.loads(row[0])


def language(text, previous=None, reservation=None):
    t=key(text)
    if re.search(r'\b(english|hello|hi|please|breakfast|pool|room|towels?|cleaning|parking|gym|password|hours|where|what|when|yes|thanks|tomorrow|now|help|front desk)\b',t):return 'en'
    if re.search(r'\b(portugues|oi|ola|obrigad[oa]|cafe|piscina|quarto|toalhas?|limpeza|estacionamento|academia|senha|horario|onde|qual|sim|nao|amanha|agora|recepcao)\b',t):return 'pt-BR'
    preferred=(previous or {}).get('language')
    if preferred:return preferred
    preferred=(reservation or {}).get('preferred_language') or (reservation or {}).get('language','')
    return 'en' if preferred.lower().startswith('en') else 'pt-BR'


def menu(topic, lang):
    icon, options=MENUS[topic]
    title='What would you like to know?' if lang=='en' else 'Como posso ajudar?'
    return response(icon+' '+title+'\n\n'+'\n'.join(f'{i}️⃣ {o[1 if lang=="en" else 0]}' for i,o in enumerate(options,1)),
                    conversation={'menu':topic})


def gap(lang):
    return response("I couldn't find that information. Would you like me to ask the front desk? 😊" if lang=='en' else
                    'Não encontrei essa informação por aqui. Quer que eu peça ajuda à recepção? 😊',
                    conversation={'offer':'reception'}, answer_marker='knowledge_gap')


def prepare(db, session, text, reservation=None):
    previous=recent(db,session);lang=language(text,previous,reservation);t=key(text)
    ctx=previous.get('conversation',{})
    if previous.get('answer_mode')=='reservation_welcome':ctx={'offer':'welcome'}
    if t in ('can you speak english','english','in english','speak english'):
        return text,lang,response('Of course! 😊 How can I help?')
    if t in ('portugues','em portugues','fale portugues'):
        return text,'pt-BR',response('Claro! 😊 Como posso ajudar?')
    if ctx.get('menu') in MENUS:
        options=MENUS[ctx['menu']][1]
        matches=[o for i,o in enumerate(options,1) if t in (str(i),key(o[0]),key(o[1]))]
        if len(matches)==1:return matches[0][2],lang,None
        if t in YES|NO|{'esse','this','that'} or t.isdigit():return text,lang,menu(ctx['menu'],lang)
    if ctx.get('offer'):
        if t in YES:return ('iniciar' if ctx['offer']=='welcome' else 'quero falar com a recepcao'),lang,None
        if t in NO:return text,lang,response('No problem. Message me when you are ready! 😊' if lang=='en' else 'Tudo bem. Me chame quando quiser! 😊')
    if t in TOPICS:return text,lang,menu(TOPICS[t],lang)
    if t in ('oi','ola','bom dia','boa tarde','boa noite','hi','hello','good morning','good evening'):
        return text,lang,response(greeting(lang), conversation={})
    commands={'yes':'sim','yes please':'sim','sure':'sim','no':'nao','now':'agora','later':'depois','tomorrow':'depois','amanha':'depois',
              'confirm name':'confirmar nome','confirm details':'confirmar dados','correct':'corrigir','finish':'concluir','start':'iniciar',
              'towel':'quero toalha','towels':'quero toalhas','toalha':'quero toalha','cleaning':'quero limpeza','front desk':'quero recepcao',
              'thanks':'obrigado','thank you':'obrigado','my booking':'minha reserva','request checkout':'quero checkout',
              'my request status':'como esta meu pedido','i received the towels':'recebi as toalhas','i did not receive the towels':'nao recebi as toalhas'}
    if reservation and reservation.get('stage') in ('OFFER','NAME','DOCUMENT','REVIEW_FINAL'):
        if t in YES: return 'sim',lang,None
        if t in NO: return ('depois' if reservation['stage']=='OFFER' else 'nao'),lang,None
    if t in commands:return commands[t],lang,None
    if t in YES|NO|{'esse','this','that','horario','hours'}:
        return text,lang,response('Which subject do you mean?' if lang=='en' else 'Sobre qual assunto você está falando?')
    # Only interpretation changes; no actions bypass their existing handlers.
    translated=text
    for pattern,value in [(r'what time|opening hours|hours','horario'),(r'wi-?fi password','senha do wifi'),
                          (r'connection help|how to connect','como conectar'),(r'breakfast','cafe da manha'),
                          (r'pool','piscina'),(r'gym','academia'),(r'parking','estacionamento'),(r'restaurant','restaurante'),
                          (r'where is|where','local'),(r'menu','cardapio'),(r'rules','regras'),
                          (r'(?:i need|i want|please bring)(?: me)?','quero'),(r'towels?','toalhas'),
                          (r'cleaning','limpeza'),(r'not working|does not work','nao funciona'),(r'front desk','recepcao')]:
        translated=re.sub(r'\b(?:'+pattern+r')\b',value,translated,flags=re.I)
    return translated,lang,None


def greeting(lang):
    hotel=hotel_profile.guest_profile()['hotel_name']
    return f"Hi! I'm the Hostess at {hotel}. 👋 How can I help?" if lang=='en' else f'Olá! Sou a Hostess do {hotel}. 👋 Como posso ajudar?'


def welcome(reservation,lang):
    name=reservation['guest_name'].split()[0];hotel=hotel_profile.guest_profile()['hotel_name']
    if lang=='en':return f"Hi, {name}! 👋 Welcome to {hotel}.\nI'm your Hostess. Shall we start your pre-check-in?\n\n1️⃣ Yes\n2️⃣ Not now"
    return f'Olá, {name}! 👋 Bem-vindo(a) ao {hotel}.\nSou sua Hostess. Quer adiantar seu pré-check-in?\n\n1️⃣ Sim\n2️⃣ Agora não'


def fact(question,lang):
    """Extract facts from the current approved source; unsupported shapes fail closed."""
    q=key(question);pid=None
    for pattern,candidate in [('wifi|wi fi|internet','POL-07'),('cafe|breakfast','POL-08'),('piscina','POL-12'),('academia','POL-15'),('estacionamento','POL-19'),('check in|check out','POL-04')]:
        if re.search(r'\b(?:'+pattern+r')\b',q):pid=candidate;break
    if not pid:return None
    policies,version=knowledge.load_base();p=policies.get(pid)
    if not p or p.get('audience')!='guest':return None
    content=p['content'];answer=None
    if pid=='POL-08':
        m=re.search(r'(?:café da manhã.*?)?servido no (.+?) de segunda a sexta, das (\d{2}h\d{0,2}) às (\d{2}h\d{0,2}), e aos sábados, domingos e feriados, das (\d{2}h\d{0,2}) às (\d{2}h\d{0,2})',content,re.I)
        if m and re.search(r'horario|horas|hours|time',q):
            place,a,b,c,d=m.groups();answer=(f'☕ Mon–Fri: {a}–{b}. Weekends and holidays: {c}–{d}.' if lang=='en' else f'☕ Segunda a sexta: {a}–{b}. Fins de semana e feriados: {c}–{d}.')
        elif m and re.search(r'local|onde|where',q):answer='☕ '+m[1]+'.'
    elif pid=='POL-07':
        network=re.search(r'rede chama-se ([^.\n]+)\.',content)
        access='O acesso utiliza o sobrenome do responsável pela reserva e o número da acomodação.'
        if network and access in content and re.search(r'senha|conectar|acesso|password',q):
            answer=(f'📶 Network: {network[1]}. Use the booking holder’s surname and room number.' if lang=='en' else f'📶 Rede: {network[1]}. Use o sobrenome do responsável pela reserva e o número do quarto.')
    elif pid=='POL-04' and 'horario' in q:
        m=re.search(r'check-in começa às (\d{1,2}h\d{0,2}) e o check-out termina às (\d{1,2}h\d{0,2})',content)
        if m:answer=(f'🧳 Check-in: {m[1]}. Checkout: {m[2]}.' if lang=='en' else f'🧳 Check-in: {m[1]}. Checkout: {m[2]}.')
    elif pid=='POL-15' and ('horario' in q or q in ('academia','gym')):
        m=re.search(r'academia funciona das (\d{2}h\d{0,2}) às (\d{2}h\d{0,2}); a idade mínima desacompanhada é de (\d+) anos',content)
        if m:answer=(f'Gym: {m[1]}–{m[2]}. Minimum age without supervision: {m[3]}.' if lang=='en' else f'Academia: {m[1]}–{m[2]}. Idade mínima sem acompanhante: {m[3]} anos.')
    elif pid=='POL-12' and 'horario' in q:
        m=re.search(r'piscina principal funciona das (\d{2}h) às (\d{2}h), a infinity das (\d{2}h) às (\d{2}h), a infantil das (\d{2}h) às (\d{2}h) e a área adults only, para maiores de (\d+) anos, das (\d{2}h) às (\d{2}h)',content)
        if m:
            a,b,c,d,e,f,age,g,h=m.groups()
            answer=(f'🏊 Main: {a}–{b}; infinity: {c}–{d}; children: {e}–{f}; adults ({age}+): {g}–{h}. Closures override these hours.' if lang=='en' else f'🏊 Principal: {a}–{b}; infinity: {c}–{d}; infantil: {e}–{f}; adultos ({age}+): {g}–{h}. Interdições prevalecem sobre os horários.')
    if not answer:return None
    if not __import__('operating_mode').production():answer=('Demo: ' if lang=='en' else 'Demonstração: ')+answer
    return dict(route='AUTO_REPLY',reply=answer,policy_ids=[pid],sources=[{'id':pid,'title':p['title']}],answer_mode='local_knowledge',knowledge_version=version,ai_used=False)


def present(result,lang,question,db,session):
    result['language']=lang
    if result.get('suppress_response'):return result
    if result.get('priority')=='urgent':
        result['reply']=('Seek help from on-site staff or local emergency services now. This chat does not dispatch emergency assistance.' if lang=='en' else 'Procure agora a equipe presencial ou o serviço de emergência da região. Este chat não aciona socorro.')
    elif result['route']=='SAFE_REPLY':
        result['reply']=('Please do not send personal passwords, documents or payment details here. Ask the front desk for secure assistance.' if lang=='en' else 'Não envie senhas pessoais, documentos ou dados de pagamento por aqui. A recepção pode ajudar com segurança.')
    elif result['route']=='HUMAN_HANDOFF':
        code=__import__('conversation_state').public_protocol(db,'interaction:'+result['request_id'])
        towels='toalha' in key(question)
        result['reply']=(("I've registered your request. The team must verify your stay before delivery." if towels else "I've registered your request for the team. Please wait for confirmation.")+f' Reference: {code}.' if lang=='en' else ('Registrei seu pedido. A equipe precisa conferir sua hospedagem antes da entrega.' if towels else 'Registrei seu pedido para a equipe. Aguarde a confirmação.')+f' Protocolo: {code}.')
    elif result.get('answer_mode')=='welcome':result['reply']=greeting(lang)
    elif result.get('answer_mode')=='local_knowledge':
        short=fact(question,lang)
        if short:result.update(short)
        elif lang=='en':result.update(gap(lang))
        elif len(result['reply'])>480:
            # Keep complete sentences; do not cut a policy mid-condition.
            result.update(gap(lang))
    elif result.get('answer_mode')=='reservation':
        import reservations
        r=reservations.bound_reservation(db,session)
        t=key(result['reply'])
        if r and result['route']!='HUMAN_HANDOFF':
            stage=r.get('stage')
            if stage=='OFFER':result['reply']=('Would you like to start pre-check-in?\n1️⃣ Yes\n2️⃣ Not now' if lang=='en' else 'Gostaria de realizar seu pré-check-in agora?\n1️⃣ Sim\n2️⃣ Agora não')
            elif stage=='NAME':result['reply']=(f"Is the booking name {r['guest_name']} correct? Reply YES or CORRECT." if lang=='en' else f"O nome da reserva é {r['guest_name']}. Está correto? Responda SIM ou CORRIGIR.")
            elif stage=='DOCUMENT':result['reply']=('Confirm that the booking details are yours: CONFIRM DETAILS or CORRECT. Show your document at the front desk; do not send it here.' if lang=='en' else 'Confirme que os dados da reserva são seus: CONFIRMAR DADOS ou CORRIGIR. Apresente o documento na recepção; não envie por aqui.')
            elif stage=='REVIEW_FINAL':result['reply']=((f"Arrival: {r['arrival'] or '—'}. Departure: {r['departure'] or '—'}. Reply FINISH; check-in still requires the front desk." if lang=='en' else f"Chegada: {r['arrival'] or '—'}. Saída: {r['departure'] or '—'}. Responda CONCLUIR; o check-in ainda depende da recepção."))
            elif lang=='en':
                if 'checkout registrado' in t or r['status']=='CHECK_OUT_REALIZADO':result['reply']='Checkout recorded. Please return your keys to the front desk.'
                elif r['checkin_status']=='CHECK_IN_REALIZADO':result['reply']='Your check-in is complete.'+(f" Room: {r['room']}." if r['room'] else '')
                elif r['pre_status']=='PRE_CHECKIN_CONCLUIDO':result['reply']='Your pre-check-in is complete. Show your identity document at the front desk on arrival.'
                else:result['reply']='Your pre-check-in is pending. Send PRE-CHECK-IN to begin.'
    elif lang=='en' and result.get('answer_mode')=='courtesy':result['reply']="You're welcome! 😊"
    elif lang=='en' and result.get('answer_mode','').startswith('service_'):
        translations={'service_cancelled':'Your towel request was cancelled.','service_feedback':'Your feedback has been recorded for the team.'}
        if result['answer_mode'] in translations:result['reply']=translations[result['answer_mode']]
        else:
            text=result['reply']
            for a,b in [('aguardando atendimento','waiting for the team'),('em atendimento','in progress'),('concluído pela equipe','completed by the team'),('cancelado pelo hóspede','cancelled by guest')]:text=text.replace(a,b)
            result['reply']=text if re.search(r'HA-\d+',text) else 'No request found in this conversation. How can I help?'
    if result.get('answer_marker')=='knowledge_gap':result['answer_mode']='knowledge_gap'
    return result
