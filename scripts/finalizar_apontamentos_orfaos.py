"""
Script para identificar e finalizar apontamentos órfãos no banco de dados.
Apontamentos órfãos são aqueles que estão abertos (data_fim = NULL) mas a OS já está finalizada ou em Expedição.
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from models import db, ApontamentoProducao, OrdemServico, StatusProducaoOS
from datetime import datetime, timedelta
from sqlalchemy import and_, or_

app = create_app()

def local_now_naive():
    """Retorna datetime naive no timezone local"""
    from datetime import timezone
    try:
        from zoneinfo import ZoneInfo
        LOCAL_TZ = ZoneInfo("America/Sao_Paulo")
    except:
        LOCAL_TZ = timezone(timedelta(hours=-3))
    return datetime.now(LOCAL_TZ).replace(tzinfo=None)

def identificar_apontamentos_orfaos():
    """Identifica apontamentos órfãos no banco de dados"""
    with app.app_context():
        print("=" * 80)
        print("IDENTIFICANDO APONTAMENTOS ÓRFÃOS")
        print("=" * 80)
        
        # 1. Apontamentos abertos em OS que estão em Expedição
        apontamentos_expedicao = db.session.query(ApontamentoProducao).join(
            OrdemServico, ApontamentoProducao.ordem_servico_id == OrdemServico.id
        ).filter(
            ApontamentoProducao.data_fim.is_(None),
            ApontamentoProducao.tipo_acao.in_(['inicio_setup', 'inicio_producao', 'pausa']),
            OrdemServico.status == 'Expedição'
        ).all()
        
        print(f"\n1. Apontamentos abertos em OS na Expedição: {len(apontamentos_expedicao)}")
        for ap in apontamentos_expedicao:
            print(f"   - ID: {ap.id} | OS: {ap.ordem_servico_id} | Tipo: {ap.tipo_acao} | Data: {ap.data_hora}")
        
        # 2. Apontamentos abertos em OS finalizadas (status Concluído ou similar)
        apontamentos_finalizadas = db.session.query(ApontamentoProducao).join(
            OrdemServico, ApontamentoProducao.ordem_servico_id == OrdemServico.id
        ).filter(
            ApontamentoProducao.data_fim.is_(None),
            ApontamentoProducao.tipo_acao.in_(['inicio_setup', 'inicio_producao', 'pausa']),
            or_(
                OrdemServico.status == 'Concluído',
                OrdemServico.status == 'Finalizado',
                OrdemServico.status == 'Arquivado'
            )
        ).all()
        
        print(f"\n2. Apontamentos abertos em OS finalizadas: {len(apontamentos_finalizadas)}")
        for ap in apontamentos_finalizadas:
            print(f"   - ID: {ap.id} | OS: {ap.ordem_servico_id} | Tipo: {ap.tipo_acao} | Data: {ap.data_hora}")
        
        # 3. Apontamentos muito antigos (mais de 7 dias abertos)
        data_limite = local_now_naive() - timedelta(days=7)
        apontamentos_antigos = db.session.query(ApontamentoProducao).filter(
            ApontamentoProducao.data_fim.is_(None),
            ApontamentoProducao.tipo_acao.in_(['inicio_setup', 'inicio_producao', 'pausa']),
            ApontamentoProducao.data_hora < data_limite
        ).all()
        
        print(f"\n3. Apontamentos abertos há mais de 7 dias: {len(apontamentos_antigos)}")
        for ap in apontamentos_antigos:
            dias_aberto = (local_now_naive() - ap.data_hora).days
            print(f"   - ID: {ap.id} | OS: {ap.ordem_servico_id} | Tipo: {ap.tipo_acao} | Aberto há {dias_aberto} dias")
        
        # 4. Total de apontamentos únicos órfãos
        todos_orfaos = set()
        for ap in apontamentos_expedicao + apontamentos_finalizadas + apontamentos_antigos:
            todos_orfaos.add(ap.id)
        
        print(f"\n{'=' * 80}")
        print(f"TOTAL DE APONTAMENTOS ÓRFÃOS ÚNICOS: {len(todos_orfaos)}")
        print(f"{'=' * 80}")
        
        return list(todos_orfaos)

def finalizar_apontamentos_orfaos(apontamento_ids, dry_run=True):
    """Finaliza apontamentos órfãos"""
    with app.app_context():
        print("\n" + "=" * 80)
        if dry_run:
            print("SIMULAÇÃO DE FINALIZAÇÃO (DRY RUN)")
        else:
            print("FINALIZANDO APONTAMENTOS ÓRFÃOS")
        print("=" * 80)
        
        agora = local_now_naive()
        finalizados = 0
        
        # Desabilitar autoflush para evitar problemas com audit log fora de request context
        db.session.autoflush = False
        
        for ap_id in apontamento_ids:
            ap = db.session.get(ApontamentoProducao, ap_id)
            if not ap:
                continue
            
            # Calcular tempo decorrido
            tempo_decorrido = int((agora - ap.data_hora).total_seconds())
            
            if dry_run:
                print(f"\n[SIMULAÇÃO] Finalizaria apontamento ID {ap.id}:")
                print(f"  - OS: {ap.ordem_servico_id}")
                print(f"  - Tipo: {ap.tipo_acao}")
                print(f"  - Início: {ap.data_hora}")
                print(f"  - Tempo decorrido: {tempo_decorrido}s ({tempo_decorrido // 3600}h {(tempo_decorrido % 3600) // 60}m)")
            else:
                ap.data_fim = agora
                ap.tempo_decorrido = tempo_decorrido
                finalizados += 1
                print(f"✓ Finalizado apontamento ID {ap.id} (OS {ap.ordem_servico_id})")
        
        if not dry_run:
            # Commit direto sem passar pelo audit log
            try:
                db.session.flush()
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                print(f"\n✗ Erro ao finalizar apontamentos: {e}")
                return 0
            print(f"\n{'=' * 80}")
            print(f"TOTAL FINALIZADO: {finalizados} apontamentos")
            print(f"{'=' * 80}")
            
            # Atualizar StatusProducaoOS para refletir estado correto
            print("\nAtualizando StatusProducaoOS...")
            os_ids = set(db.session.query(ApontamentoProducao.ordem_servico_id).filter(
                ApontamentoProducao.id.in_(apontamento_ids)
            ).distinct())
            
            for (os_id,) in os_ids:
                status = db.session.query(StatusProducaoOS).filter_by(ordem_servico_id=os_id).first()
                if status:
                    # Verificar se ainda há apontamentos abertos
                    abertos = db.session.query(ApontamentoProducao).filter(
                        ApontamentoProducao.ordem_servico_id == os_id,
                        ApontamentoProducao.data_fim.is_(None),
                        ApontamentoProducao.tipo_acao.in_(['inicio_setup', 'inicio_producao', 'pausa'])
                    ).count()
                    
                    if abertos == 0:
                        status.status_atual = 'Aguardando'
                        status.operador_atual_id = None
                        status.item_atual_id = None
                        status.trabalho_atual_id = None
                        status.inicio_acao = None
                        status.motivo_pausa = None
                        print(f"  ✓ StatusProducaoOS da OS {os_id} atualizado para 'Aguardando'")
            
            db.session.commit()
            print("\nStatusProducaoOS atualizado com sucesso!")
        
        return finalizados

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Finalizar apontamentos órfãos')
    parser.add_argument('--execute', action='store_true', help='Executar finalização (sem este flag, apenas simula)')
    args = parser.parse_args()
    
    # Identificar órfãos
    orfaos_ids = identificar_apontamentos_orfaos()
    
    if not orfaos_ids:
        print("\n✓ Nenhum apontamento órfão encontrado!")
        sys.exit(0)
    
    # Perguntar confirmação se for executar
    if args.execute:
        print("\n" + "!" * 80)
        print("ATENÇÃO: Você está prestes a FINALIZAR os apontamentos órfãos!")
        print("!" * 80)
        resposta = input("\nDeseja continuar? (digite 'SIM' para confirmar): ")
        if resposta.strip().upper() != 'SIM':
            print("\nOperação cancelada pelo usuário.")
            sys.exit(0)
        
        finalizar_apontamentos_orfaos(orfaos_ids, dry_run=False)
    else:
        print("\n" + "=" * 80)
        print("MODO SIMULAÇÃO - Use --execute para finalizar de verdade")
        print("=" * 80)
        finalizar_apontamentos_orfaos(orfaos_ids, dry_run=True)
