"""Create the initial local administrator once; never print its password."""
import os
import secrets
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import app
import auth

def main():
    app.init_db()
    with app.connection() as db:
        exists=db.execute('SELECT 1 FROM staff_users LIMIT 1').fetchone()
    local=Path(os.environ['LOCALAPPDATA'])/'AURA'
    local.mkdir(parents=True,exist_ok=True)
    access=local/'initial-access.txt'
    if not exists:
        password=secrets.token_urlsafe(20)
        # File first: if account creation fails, a later run replaces the unused secret.
        access.write_text('AURA - primeiro acesso\nURL: http://localhost:8787/login\nLogin: uiliam\nSenha temporaria: '+password+'\nTroque a senha no primeiro acesso. Apague este arquivo depois da troca.\n',encoding='utf-8')
        auth.create_user(app.connection,dict(username='uiliam',name='Uiliam',role='admin',password=password))
        print('Administrador criado. Acesso inicial salvo somente no perfil local do Windows.')
    else:
        print('Contas existentes preservadas.')
    token=app.ROOT/'runtime/auth/service-token.txt'
    token.parent.mkdir(parents=True,exist_ok=True)
    if not token.exists(): token.write_text(secrets.token_urlsafe(48),encoding='utf-8')
    print('Credencial de integracao local pronta; nenhum segredo exibido.')

if __name__=='__main__': main()
