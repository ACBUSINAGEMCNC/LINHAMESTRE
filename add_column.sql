-- Script SQL para adicionar coluna pode_gerenciar_apontamentos
-- Execute este script diretamente no Supabase SQL Editor ou via psql

-- Verificar se a coluna já existe
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 
        FROM information_schema.columns 
        WHERE table_name='usuario' 
        AND column_name='pode_gerenciar_apontamentos'
    ) THEN
        -- Adicionar coluna
        ALTER TABLE usuario 
        ADD COLUMN pode_gerenciar_apontamentos BOOLEAN DEFAULT FALSE;
        
        RAISE NOTICE 'Coluna pode_gerenciar_apontamentos adicionada com sucesso!';
    ELSE
        RAISE NOTICE 'Coluna pode_gerenciar_apontamentos já existe.';
    END IF;
END $$;

-- Verificar resultado
SELECT column_name, data_type, column_default
FROM information_schema.columns 
WHERE table_name='usuario' 
AND column_name='pode_gerenciar_apontamentos';
