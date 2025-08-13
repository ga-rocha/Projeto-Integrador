import os
import secrets

# Chave secreta para sessões e tokens
SECRET_KEY = os.getenv("SECRET_KEY", secrets.token_hex(32))

# Strings de conexão com SQL Server
SQLSERVER_LOCAL = os.getenv("SQLSERVER_LOCAL", "mssql+pyodbc://sa:unifai2022@localhost/SistemaAltasdePaciente_Gabriel_Rocha_Melo_RA_026823?driver=ODBC+Driver+17+for+SQL+Server")
