# RoboAdmin-AI

!!!Application is still under development!!!

RoboAdmin-AI is a local multi-agent AI workbench for IT operations. It runs entirely on your machine — no cloud, no API keys, no data leaving your network.
Built with PySide6 + smolagents + Ollama.

##System engineering/administration
test_apache.png

##Network Engineering
test_network.png

##DBA or SQL queries
test_database.png
test_sql_query.png

Recommended model - Qwen2.5:14b or above. Install Ollama from official website. 

Three specialised agents collaborate under a manager:

*System Engineer – service checks, Linux config generation, Dockerfiles.
*Network Engineer – Network audits, config creating and parsing.
*DBA Engineer – Schema inspection & read-only SQL queries.

Some examples how to use:

Server config:
Generate a production-ready, secure Apache HTTP Server configuration file based on the parameters below.

Network config based on a file(if exists):
Analyze the provided core_switch.txt. Generate a configuration for a Cisco 2960 access switch, including access.
switch ports, trunk ports, access vlans, management vlans,user credentials, enable ssh, set hostname as Access-Switch-2960.

Database analysis or sql queries:
Analyze the provided test_db.sql PostgreSQL script and list all tables defined inside it. 
Requiremetns: 
1. For each table, provide: -It's exact name. - A brief, 1-sentence description of its purpose in the buisness logic.
2. Identify and highlight any indexes created in the script.
3. Present your findings in a highly readable markdown format with tables or clear bullet points.

!!!May not work properly currently!!!
Test configuration in Docker(required Docker installed and running):
Configure Nginx(8080) and test endpoints in Docker.


Point it at your .txt, .cfg files, a Docker socket, or a local database and ask questions in plain English. 
Everything executes locally via Ollama (Qwen 2.5 / Llama 3 / Mistral — your pick).
