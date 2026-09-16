window.auraStaff = (async()=>{
 const response=await fetch('/api/auth/me');
 if(!response.ok){if(location.pathname!=='/')location.replace('/login');return null}
 const user=await response.json();
 if(user.must_change){location.replace('/login');return null}
 const links={'/recepcao':'reception','/politicas':'policies','/operacao':'operations','/equipe':'users'};
 document.querySelectorAll('nav a').forEach(a=>{const p=links[a.getAttribute('href')];if(p&&!user.permissions.includes(p))a.hidden=true});
 const nav=document.querySelector('nav');
 if(nav){if(user.permissions.includes('users')){const a=document.createElement('a');a.href='/equipe';a.textContent='Equipe e piloto';nav.append(a)}
 const label=document.createElement('span');label.textContent=user.name+' ('+user.username+')';nav.append(label);
 const password=document.createElement('a');password.href='/login';password.textContent='Minha senha';nav.append(password);
 const exit=document.createElement('button');exit.textContent='Sair';exit.onclick=async()=>{await fetch('/api/auth/logout',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});location.href='/login'};nav.append(exit)}
 for(const id of ['operator','actor']){const field=document.getElementById(id);if(field){field.value=user.username;field.readOnly=true;field.oninput=null}}
 return user;
})();
