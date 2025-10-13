@echo off

REM Mude para o diretório do seu projeto Django
cd "C:\Django"

REM Ative o ambiente virtual. Este é o comando padrão.
REM A ativação aqui serve mais para garantir o contexto, embora não seja
REM estritamente necessária se chamarmos o python.exe diretamente.
call ".venv\Scripts\activate"

REM Execute o comando do Django usando o python.exe do ambiente virtual.
REM Este é o passo mais importante.
"C:\Django\.venv\Scripts\python.exe" manage.py update_overdue

REM Opcional: Pausa a janela do console se você quiser ver a saída ao
REM executar manualmente. O Agendador de Tarefas ignora isso.
REM pause