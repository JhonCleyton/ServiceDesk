# Guia do Sistema JC Service Desk

Este guia orienta o uso do sistema de Service Desk: autenticação, tickets, chat, notificações, mini‑jogos da sala de espera, LGPD e administração.


## 1. Acesso e Autenticação

- **Cadastro**
  - Acesse “Criar conta”. Informe nome, e‑mail corporativo e empresa.
  - Algumas empresas exigem domínio específico no e‑mail.
  - Em certos casos, você deverá aceitar os termos (LGPD) para concluir o cadastro.
- **Confirmação de e‑mail**
  - Após o cadastro, você receberá um e‑mail com link de confirmação.
  - Clique para validar a conta antes do primeiro login.
- **Login**
  - Informe e‑mail e senha cadastrados.
  - O sistema pode aplicar bloqueio temporário após várias tentativas inválidas.
  - Algumas empresas/contas restringem login por IP (permitidos pela empresa).
- **Verificação em duas etapas (OTP)**
  - Quando habilitada pela conta, após o login enviaremos um código por e‑mail.
  - Digite o código de 6 dígitos para concluir o acesso.
- **Esqueceu a senha**
  - Na tela de login, clique em “Esqueceu a senha?”.
  - Informe seu e‑mail para receber o link de redefinição (válido por tempo limitado).


## 2. Tickets

- **Criar ticket**
  - Descreva o problema, selecione categoria/prioridade (quando disponível) e envie.
  - Você e os responsáveis recebem confirmação por e‑mail.
- **Detalhe do ticket**
  - Acompanha status, histórico e comentários.
  - Técnicos visualizam informações do cliente (nome, e‑mail, empresa) para agilizar o atendimento.
- **Comentários**
  - Envie novas informações, anexos e feedbacks.
  - Comentários podem ser públicos (visíveis ao cliente) ou internos (apenas equipe), conforme disponibilidade.
- **Atribuição e Andamentos**
  - Técnicos podem assumir, resolver e encerrar tickets.
  - Ações enviam e‑mails de atualização quando aplicável.
- **Encerramento e Avaliação**
  - No fechamento, técnicos registram avaliação técnica (categoria/comentário).
  - O cliente pode avaliar o atendimento (nota/comentário) via link seguro.


## 3. Chat em Tempo Real

- Canal integrado ao ticket/ambiente com atualização em tempo real (SSE).
- Use para conversas rápidas com a equipe. Histórico fica vinculado.


## 4. Notificações

- **Sino de notificações** na barra superior exibe novas atividades: comentários, mudanças de status, menções, etc.
- **Tempo real (SSE)** com fallback para polling quando necessário.
- **Marcar como lida** individualmente ou “Marcar todas como lidas”.
- Contador de não lidas é atualizado automaticamente.


## 5. Sala de Espera e Mini‑jogos

- Ao aguardar atendimento, utilize os mini‑jogos integrados:
  - **Snake** com melhorias de UX, controle de foco e exibição de velocidade.
  - **Sudoku** com gerador/solver, níveis de dificuldade e validações de conflitos.
- Há mecanismos básicos de anti‑trapaça; placares exibem os melhores resultados.


## 6. LGPD (Política de Privacidade)

- **Público:** página com a versão vigente da política de privacidade.
- **Admin:** gestão de revisões (criar, publicar/despublicar) com histórico e auditoria.
- Usuários podem precisar aceitar termos/consentimento ao se registrar.


## 7. Base de Conhecimento e Relatórios

- **Base de Conhecimento (KB):** artigos de apoio (quando habilitada pela empresa).
- **Relatórios:** visão analítica para administradores/gestores (quando habilitado).


## 8. E‑mails

- Enviamos e‑mails para: confirmação de cadastro, OTP (2FA), confirmações/comentários de tickets, mudanças de status e **redefinição de senha**.
- Conteúdos podem ser personalizados por empresa via modelos de e‑mail (quando habilitado).


## 9. Dicas de Uso

- Mantenha seus dados atualizados e verifique seu e‑mail regularmente.
- Utilize comentários públicos para comunicação com o cliente e internos para alinhamento da equipe.
- Em caso de dúvidas sobre privacidade, consulte a página LGPD e o DPO informado.


## 10. Suporte

- Para suporte, utilize o próprio sistema de tickets.
- Em casos de indisponibilidade, utilize o canal de WhatsApp destacado na interface.
Manual do Sistema por Menu


## 11. Atualizações recentes

- Listagem profissional para técnicos: separa "Sem atendimento" (não atribuídos) e "Em atendimento" (com responsável), agrupando por empresa e exibindo o técnico responsável.
- Restrições de interação: apenas o técnico responsável e perfis autorizados (admin/supervisor) podem assumir/resolver/encerrar; participantes colaboram, principalmente via comentários internos.
- Participantes e transferência: convite/remoção de técnicos participantes no ticket e botão de transferência rápida do responsável.
- Chat interno: opção "Interno" para mensagens visíveis somente à equipe.
- Sudoku: cronômetro e sistema de vidas (fácil=5, médio=3, difícil=1); erros não bloqueiam o jogo, apenas marcam a célula e consomem 1 vida; término ao zerar vidas.




• Dashboard
O que é: Página inicial com atalhos e visão geral.
Para que serve: Acessar rapidamente as principais áreas (Chamados, KB, Admin, Relatórios).
Quem usa: Todos os perfis autenticados.
• Chamados > Listar
O que é: Lista de chamados, do mais recente para o mais antigo.
Para que serve: Consultar chamados. Perfis internos (admin/supervisor/técnico) veem todos; cliente vê apenas os próprios.
Ações principais: Abrir o detalhe, acompanhar prazos de SLA, ver comentários e anexos.
• Chamados > Criar
O que é: Formulário para abrir um novo chamado.
Para que serve: Registrar demandas com título, descrição, prioridade, categoria, contrato (se houver), fila/equipe e ativo.
Por que: Inicia o ciclo de atendimento e aciona prazos de SLA automaticamente conforme regras da empresa/contrato.
Ações: Enviar anexos, direcionar à fila certa, criar com o ativo impactado.
• Base de Conhecimento > Pesquisar
O que é: Lista de artigos e busca.
Para que serve: Ajudar a resolver problemas recorrentes com guias e soluções.
Quem usa: Todos (leitura).
• Base de Conhecimento > Novo artigo
O que é: Formulário de criação de artigo.
Para que serve: Registrar conhecimento.
Quem usa: admin, supervisor, técnico (controle de publicação interna).
• Chat
O que é: Canal de conversas do sistema (com webhook de WhatsApp stub).
Para que serve: Centralizar conversas relacionadas ao suporte.
Quem usa: Equipe interna; pode ser expandido para usuários finais.
• Admin > Dashboard
O que é: Painel de administração com atalhos para módulos de gestão.
Para que serve: Centralizar a administração do sistema.
• Admin > Empresas
O que é: Gestão de empresas (multi-tenant).
Para que serve: Definir domínio de e-mail (valida cadastros), termos de uso, se exige consentimento, dias de retenção (LGPD) e allowlist de IP.
Por que: Segurança, conformidade e isolamento por empresa.
• Admin > Usuários
O que é: Gestão de usuários (criar/editar).
Para que serve: Definir perfil (cliente, técnico, supervisor, admin), empresa, confirmação e exigência de 2FA.
Por que: Controle de acesso e segurança.
• Admin > Categorias
O que é: Taxonomia de chamados.
Para que serve: Classificar chamados para roteamento, métricas e conhecimento.
• Admin > Contratos
O que é: Gestão de contratos de atendimento.
Para que serve: Parametrizar atendimento por cliente (SLA, escopo).
• Admin > Planos de SLA
O que é: Regras de prazo (primeira resposta e resolução).
Para que serve: Controlar e medir o cumprimento de SLA por prioridade/categoria/contrato.
• Admin > Filas/Equipes
O que é: Estrutura de atendimento por fila/equipe.
Para que serve: Direcionar chamados à equipe responsável e facilitar distribuição de trabalho.
• Admin > Ativos
O que é: Cadastro de ativos/equipamentos.
Para que serve: Relacionar chamados aos ativos impactados (rastreabilidade).
• Admin > Modelos de E-mail
O que é: Templates de assunto e corpo por empresa e tipo de evento.
Para que serve: Personalizar comunicações (criação de chamado, comentários, status, OTP).
Observação: Suportam variáveis do contexto (número, título, link, autor, etc.).
• Admin > Problemas
O que é: Gestão de problemas (ITIL Problem Management).
Para que serve: Tratar causas raiz e recorrências de incidentes.
• Admin > Mudanças
O que é: Gestão de mudanças (Change Management).
Para que serve: Controlar alterações planejadas e seu impacto nos serviços.
• Admin > Ferramentas
O que é: Utilitários administrativos.
Para que serve: Executar rotinas como leitura IMAP (e-mail -> ticket), automações e retenção/anonimização (LGPD).
• Relatórios
O que é: Área de relatórios.
Para que serve: Análises e métricas (SLA, volume, filas, etc.).
• Autenticação (Entrar / Cadastrar / OTP)
Cadastro: Valida domínio da empresa e, se exigido, exige aceite de termos.
Confirmação por e-mail: Usuário deve confirmar o e-mail para acessar.
2FA: Se “Exigir 2FA” estiver habilitado, o login solicita código OTP por e-mail.