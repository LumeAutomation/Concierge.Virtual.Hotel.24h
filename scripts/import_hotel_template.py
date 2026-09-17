"""Import a data-only hotel template into a NEW AURA database as policy drafts."""
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import app,hotel_profile

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--template',type=Path,required=True)
    parser.add_argument('--database',type=Path,required=True)
    args=parser.parse_args()
    package=json.loads(args.template.read_text(encoding='utf-8-sig'));hotel_profile.validate_template(package)
    destination=args.database.resolve()
    if destination.exists():parser.error('O banco de destino já existe. Informe um arquivo novo em uma instalação separada.')
    destination.parent.mkdir(parents=True,exist_ok=True)
    # Exclusive creation prevents two imports from accidentally sharing a destination.
    with destination.open('xb'):pass
    app.DB=destination;app.init_db()
    result=hotel_profile.import_new(app.connection,package,'implantacao')
    print(json.dumps(result,ensure_ascii=True))
    print('Modelo importado como rascunhos. Crie acessos próprios, revise as políticas e configure serviços exclusivos nesta instalação.')
if __name__=='__main__':main()
