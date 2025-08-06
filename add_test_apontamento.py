from app import create_app
from models import StatusProducaoOS, OrdemServico
from datetime import datetime
import pytz

app = create_app()

with app.app_context():
    # Get the first order service
    ordem = OrdemServico.query.first()
    if ordem:
        # Check if there's already a status for this order service
        status = StatusProducaoOS.query.filter_by(ordem_servico_id=ordem.id).first()
        if not status:
            # Create a new status if it doesn't exist
            status = StatusProducaoOS(ordem_servico_id=ordem.id)
            print(f'Created status for OS {ordem.id}')
        else:
            print(f'Status already exists for OS {ordem.id}')
        
        # Set the status to "Setup em andamento" with current time
        status.status_atual = 'Setup em andamento'
        status.inicio_acao = datetime.now(pytz.UTC)
        print(f'Set status to {status.status_atual} with inicio_acao: {status.inicio_acao}')
    else:
        print('No order service found in database')
