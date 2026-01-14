# Teste de Destaque de Quantidade Alterada - Item Composto

## Passos para testar:

1. **Reinicie o servidor**
   ```
   Ctrl+C (parar servidor)
   python run.py
   ```

2. **Identifique um pedido de item composto**
   - Vá em `/pedidos`
   - Encontre um pedido de item composto (ex: ACB-XXX que tenha componentes)
   - Anote o número do pedido e a quantidade atual

3. **Altere a quantidade do pedido**
   - Edite o pedido e mude a quantidade (ex: de 10 para 15)
   - Salve

4. **Abra o Kanban**
   - Vá para `/kanban`
   - Encontre a OS do **componente** deste item composto
   - Clique para abrir os detalhes

5. **Verifique os logs no terminal**
   - Os logs vão mostrar:
     - Se o pedido AUTO foi detectado
     - Se o ID do pedido original foi extraído
     - Se o item composto foi encontrado
     - A quantidade esperada vs atual
     - Se a mudança foi detectada

6. **Verifique o destaque visual**
   - A linha deve ficar **amarela**
   - Deve aparecer badge **"⚠️ Alterado"**

## O que os logs devem mostrar:

```
PedidoOS XXX: Pedido virtual AUTO detectado: AUTO-OS-2025-XXX-YYY
PedidoOS XXX: ID pedido original extraído: YYY
PedidoOS XXX: Pedido original encontrado, item_id: ZZZ
PedidoOS XXX: Item composto encontrado: ACB-XXX
PedidoOS XXX: Qtd esperada=15, Qtd atual=10, Snapshot=10
PedidoOS XXX: QUANTIDADE ALTERADA DETECTADA! Esperada=15, Atual=10
```

## Se não funcionar:

Copie os logs do terminal e me envie para análise.
