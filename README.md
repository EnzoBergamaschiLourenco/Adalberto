# 📧 Parser de E-mails XpertPlan & Integração Umov.me

Este sistema é uma solução robusta e automatizada para triagem de e-mails, extração inteligente de dados de Notas Fiscais Eletrônicas (NF-e) via OCR e integração bidirecional com a plataforma **Umov.me**.

O objetivo principal é eliminar processos manuais de redigitação de informações logísticas, convertendo PDFs de DANFE em dados estruturados e atualizando de forma dinâmica os agendamentos (*schedules*) de entregas de **Peças** e **Tubos**.

---

## 🏗️ Arquitetura do Sistema

O projeto é modularizado em quatro pilares fundamentais:

```text
├── main.py                # Interface gráfica web desenvolvida em Streamlit
├── email_parser.py        # Motor de conexão IMAP e extração de chaves via OCR
├── pecas.py               # Regras de negócio e integração Umov.me para o fluxo de Peças
├── tubos.py               # Regras de negócio e integração Umov.me para o fluxo de Tubos
└── dictionaries.py        # Dicionários auxiliares (Mapeamentos de motoristas, CNPJs, etc.)

```

---

## 🌟 Principais Funcionalidades

### 1. Triagem e Conexão de E-mails Dinâmica

* Conexão via protocolo **IMAP** seguro (`email-ssl.com.br` na porta 993).
* Filtro inteligente por intervalo de datas selecionado na interface gráfica.
* Classificação automática de fluxos baseada no assunto do e-mail:
* Assuntos contendo **"PEÇAS"** ou **"PECAS"** entram no fluxo de peças.
* Assuntos contendo **"TUBOS"** entram no fluxo de tubos.



### 2. OCR Inteligente de DANFEs (PDF para XML)

Quando um e-mail é triado, o sistema localiza os arquivos PDFs em anexo e executa um pipeline de Visão Computacional para resgatar a chave de acesso da NF-e:

* **Renderização:** O `pdfplumber` renderiza a primeira página do documento em alta definição (300 DPI).
* **Corte Estratégico (Crop):** Para otimizar o tempo de processamento e precisão, a imagem é recortada especificamente na área padrão onde se localiza o código de barras e a chave de acesso de 44 dígitos.
* **OCR com EasyOCR:** O modelo em português analisa o recorte de imagem para obter os caracteres textuais.
* **Sanitização e Regex:** Filtra-se apenas números para isolar a chave de 44 dígitos.
* **Consumo de API Externa:** A chave obtida realiza uma requisição POST para a API `consultadanfe.com`, retornando o conteúdo bruto do **XML** da Nota Fiscal codificado em Base64, que é subsequentemente decodificado.

### 3. Painel de Controle Streamlit (UI)

* Interface simples e scannável para controle de credenciais e data de processamento.
* Apresentação de resultados através de abas expansíveis (*expanders*) organizadas por e-mail processado.
* **Módulo de Auditoria Visual:** Exibição clara do remetente, número de remessa, peso total, motorista e transportadora mapeada, além do payload do XML enviado e os logs de resposta da API do Umov.me.

---

## 🔄 Fluxos de Negócio Detalhados

Abaixo estão detalhadas as duas regras de processamento distintas do ecossistema:

### Fluxo de Peças (`pecas.py`)

O fluxo de Peças é focado na **criação e atualização de agendamentos** no Umov.me com base nas notas fiscais extraídas.

```mermaid
graph TD
    A[E-mail de Peças] --> B[Extrair XML do PDF via OCR]
    B --> C[Mapear Motorista, Transportadora e CNPJ]
    C --> D[Gerar Payload <schedule> com NF e Peso]
    D --> E{Recebimento Retroativo?}
    E -- Sim --> F[Adicionar tag <BaixaManual>]
    E -- Não --> G[POST /schedule.xml no Umov.me]
    F --> G
    G --> H{Teve Baixa Manual?}
    H -- Sim --> I[GET /schedule.xml?NF=...]
    I --> J[Identificar IDs de agendamento]
    J --> K[POST /schedule/{id}.xml mudando situação para ID 50]
    H -- Não --> L[Fim do Processo]

```

1. **Mapeamento de Dados:** Lê o assunto e o corpo do e-mail para encontrar correspondência com os dicionários cadastrados:
* **Motorista (`MOTORISTA_ID`):** Define o `agent_id`.
* **Transportadora (`MOTORISTA_TRANSPORTADORA`):** Define o nome da transportadora.
* **CNPJ Cliente (`CNPJ_SERVICELOCAL`):** Procura no XML decodificado todos os CNPJs válidos e os cruza com o dicionário para obter o ID do local de serviço (`service_local_id`).


2. **Criação de Schedule (POST):** Gera um XML estruturado e envia via `POST` para criar a atividade de entrega no Umov.me.
3. **Tratamento de Retroativos (Baixa Manual):**
* Se a data de recebimento do e-mail for anterior à data atual, o sistema adiciona a tag `<BaixaManual>` no XML.
* Adicionalmente, executa uma rotina secundária: faz uma requisição `GET` para buscar registros existentes no Umov.me que compartilham da mesma Nota Fiscal (`NF`), captura os IDs internos destes registros e realiza chamadas `POST` sequenciais para atualizar o status/situação de entrega desses registros para a situação de finalizado (`id: 50`).



---

### Fluxo de Tubos (`tubos.py`)

O fluxo de Tubos é focado na **atualização de agendamentos existentes**, sem a necessidade de criar novas ordens.

1. **Localização da Remessa:** Extrai do corpo do e-mail um padrão numérico de 8 dígitos referente à remessa logitísca (`CF_Remessa`).
2. **Consulta de Agendamento por Filtro (GET):** Realiza uma requisição `GET` para a rota `/schedule.xml?CF_Remessa={remessa}` a fim de encontrar todos os agendamentos em andamento relacionados àquela carga de tubos.
3. **Atualização em Massa (POST):**
* Utiliza expressão regular para identificar todos os IDs das entradas (*entries*) retornadas no XML do GET.
* Para cada ID encontrado, realiza um disparo de `POST` enviando um payload contendo as Notas Fiscais identificadas na leitura dos PDFs (`<customFields><NF>{str_nfs}</NF></customFields>`), vinculando os documentos diretamente às respectivas viagens.



---

## 🛠️ Tecnologias e Dependências

Abaixo estão listadas as ferramentas e bibliotecas fundamentais que sustentam o projeto:

| Biblioteca | Versão Recomendada | Utilidade no Sistema |
| --- | --- | --- |
| **Streamlit** | `^1.30.0` | Interface do usuário interativa e ágil |
| **pdfplumber** | `^0.10.0` | Manipulação e renderização rasterizada do PDF |
| **easyocr** | `^1.7.0` | Engine de OCR local para detecção da chave da NF-e |
| **numpy** | `^1.24.0` | Conversão de imagens da biblioteca PIL para matrizes numéricas |
| **requests** | `^2.31.0` | Requisições HTTP para a API de DANFE e Umov.me |

---

## ⚙️ Configuração e Instalação

### 1. Variáveis de Ambiente e Segredos (Secrets)

Crie um diretório `.streamlit/` na raiz do seu projeto e adicione um arquivo `secrets.toml`. Insira a credencial da API do Umov.me:

```toml
# .streamlit/secrets.toml
umov_api_key = "SUA_CHAVE_API_UMOV_AQUI"

```

### 2. Inicializando o Sistema localmente

Com o Python instalado em seu ambiente de desenvolvimento, execute o comando abaixo no terminal para instalar as dependências necessárias:

```bash
pip install streamlit pdfplumber easyocr numpy requests

```

Para inicializar a interface web, digite o seguinte comando:

```bash
streamlit run main.py

```

Pronto! Acesse o endereço disponibilizado em seu terminal (geralmente `http://localhost:8501`) e insira suas credenciais do webmail para processar os e-mails logísticos de forma totalmente automatizada.