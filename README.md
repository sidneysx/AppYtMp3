# BaixarMp3 🎵

Aplicação web em Flask para baixar áudio do YouTube convertido em MP3, usando `yt-dlp` + `FFmpeg`.

O projeto tem **duas versões** do servidor:

| Arquivo | Comportamento |
|---|---|
| `app.py` | Salva o MP3 numa pasta fixa (`downloads/`) **no servidor** |
| `appmobile.py` | Envia o MP3 direto pro **navegador de quem clicou**, indo pra pasta de Downloads do celular/PC de quem acessa |

> 💡 Se o objetivo é rodar o servidor em um computador e baixar os arquivos em outros dispositivos na mesma rede (celular, notebook, etc), use o **`appmobile.py`**.

---

## ⚠️ Pré-requisitos obrigatórios

### 1. Python 3.10+

Verifique com:

```bash
python --version
```

### 2. FFmpeg instalado e **no PATH do sistema**

Isso é **essencial** — sem o FFmpeg no PATH, a conversão para MP3 falha.

**Windows:**

1. Baixe o FFmpeg em: https://www.gyan.dev/ffmpeg/builds/ (versão "release essentials")
2. Extraia o `.zip` em um local fixo, por exemplo `C:\ffmpeg`
3. Adicione `C:\ffmpeg\bin` ao **PATH** do Windows:
   - Pesquise por "Variáveis de Ambiente" no menu Iniciar
   - Em "Variáveis do sistema", edite a variável `Path`
   - Clique em "Novo" e adicione: `C:\ffmpeg\bin`
   - Confirme tudo com "OK"
4. **Reinicie o terminal** (ou o PC) para o PATH atualizar
5. Teste digitando no terminal:

   ```bash
   ffmpeg -version
   ```

   Se aparecer a versão do FFmpeg, está tudo certo. Se der erro de "comando não encontrado", o PATH não foi configurado corretamente.

**macOS (via Homebrew):**

```bash
brew install ffmpeg
```

**Linux (Debian/Ubuntu):**

```bash
sudo apt update && sudo apt install ffmpeg
```

> Com o FFmpeg no PATH, **não é necessário** definir `ffmpeg_location` manualmente no código — o `yt-dlp` encontra o executável automaticamente.

---

## Instalação

```bash
git clone https://github.com/sidneysx/AppYtMp3.git
cd AppYtMp3
python -m venv .venv
```

Ative o ambiente virtual:

```bash
# Windows
.venv\Scripts\activate

# macOS/Linux
source .venv/bin/activate
```

Instale as dependências:

```bash
pip install -r requirements.txt
```

---

## Como rodar

### Versão padrão (salva no servidor)

```bash
python app.py
```

### Versão para celular/rede local (baixa no dispositivo de quem acessa)

```bash
python appmobile.py
```

Ambas sobem o servidor em `http://localhost:5001`.

---

## Acessando de outros dispositivos na mesma rede (celular, notebook, etc)

1. Descubra o IP local do computador que está rodando o Flask:

   ```bash
   # Windows
   ipconfig

   # macOS/Linux
   ifconfig
   ```

   Procure por algo como `192.168.0.10` (Endereço IPv4).

2. Certifique-se de que o dispositivo (celular, outro PC) está conectado ao **mesmo Wi-Fi**.

3. No navegador do dispositivo, acesse:

   ```
   http://SEU_IP_LOCAL:5001
   ```

4. Insira a URL do vídeo e clique em baixar — o arquivo MP3 vai direto pra pasta de Downloads **daquele dispositivo** (usando `appmobile.py`).

> Se o navegador não conseguir acessar, verifique se o Firewall do computador está bloqueando a porta `5001`.

---

## Estrutura do projeto

```
BaixarMp3/
├── app.py            # Versão que salva no servidor
├── appmobile.py       # Versão que baixa no dispositivo do usuário
├── requirements.txt
├── .gitignore
├── .env.example
├── downloads/          # Criada automaticamente (ignorada pelo git)
├── static/
└── templates/
    └── index.html
```

---

## ⚠️ Aviso legal

Esta ferramenta deve ser usada apenas para baixar conteúdo próprio ou com autorização explícita do detentor dos direitos. O uso para baixar conteúdo protegido por direitos autorais sem permissão pode violar os Termos de Serviço do YouTube e legislações de direitos autorais aplicáveis.
