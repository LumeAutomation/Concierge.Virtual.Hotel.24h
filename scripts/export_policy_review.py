"""Export review material without approving any hotel policy."""
import csv
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import app
import policy_review
app.init_db()
output=app.ROOT/'runtime/policy-review-checklist.csv'
rows=policy_review.catalog(app.connection,app.POLICIES)
with output.open('w',encoding='utf-8-sig',newline='') as stream:
    writer=csv.writer(stream,delimiter=';')
    writer.writerow(['ID','Situacao','Revisao','Titulo','Departamento','Texto para revisar','Exemplo de pergunta','Responsavel do hotel','Decisao','Observacoes'])
    for row in rows:
        draft=row['draft']
        writer.writerow([row['id'],row['state'],row['revision'],draft['title'],draft['department'],draft['content'],draft['example_question'],'','',''])
print(str(len(rows))+' politicas exportadas para runtime/policy-review-checklist.csv; nenhuma aprovada automaticamente.')
