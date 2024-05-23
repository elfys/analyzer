## Installation

1. Run the following command in PowerShell to install analyzer.exe
   ```powershell
   Set-ExecutionPolicy Bypass -Scope Process -Force; Invoke-WebRequest -UseBasicParsing -Uri "https://raw.githubusercontent.com/elfys/analyzer/main/install.ps1" -OutFile "./install-analyzer.ps1"; &"./install-analyzer.ps1"; & rm "install-analyzer.ps1"
   ```
2. Restart PowerShell and run `analyzer.exe`


## Development

1. Install pyenv:
    - [Instructions](https://pyenv-win.github.io/pyenv-win/#installation) for windows
    - [Instructions](https://github.com/pyenv/pyenv#installation) for Linux and MacOS
2. Clone this repository
   `git clone https://github.com/elfys/analyzer.git`
3. Navigate to the project directory
   `cd analyzer`
4. Install proper python version
   ```shell
   pyenv update
   pyenv install $(cat .python-version)
   ```
5. Install pipenv
   ```shell
   pip install pipenv
   ```
6. Install python dependencies
   There are different options to install dependencies:

   a. Using project-specific virtual environment, suitable for development

      ```shell
      mkdir .venv
      pipenv install --dev
      ```
      To activate the new virtual environment use `pipenv shell`

   b. Using global virtual environment, suitable for prober machines
      
      ```shell
      pipenv install --deploy --system 
      ```


### Useful commands

- `pylint $(git diff --name-only  | grep '\.py$')` - run pylint linter on changed files
- `black --line-length 100 $(git diff --name-only  | grep '\.py$')` - run black formatter on changed files
- `flake8 .` - run flake8 linter
- `python -m analyzer db dump -l 100` - create a small dump
- `gzip -d dump_20230202_183945.sql.gz` - unarchive dump
- `docker compose up` - start database

## Usage

Running the installed program: `analyzer.exe --help`
Similarly, you can run the program from the source code: `python -m analyzer --help`

```
   █████╗  ███╗   ██╗  █████╗  ██╗   ██╗   ██╗ ███████╗ ███████╗ ██████╗ 
  ██╔══██╗ ████╗  ██║ ██╔══██╗ ██║   ╚██╗ ██╔╝ ╚══███╔╝ ██╔════╝ ██╔══██╗ 
  ███████║ ██╔██╗ ██║ ███████║ ██║    ╚████╔╝    ███╔╝  █████╗   ██████╔╝ 
  ██╔══██║ ██║╚██╗██║ ██╔══██║ ██║     ╚██╔╝    ███╔╝   ██╔══╝   ██╔══██╗ 
  ██║  ██║ ██║ ╚████║ ██║  ██║ ███████╗ ██║    ███████╗ ███████╗ ██║  ██║ 
  ╚═╝  ╚═╝ ╚═╝  ╚═══╝ ╚═╝  ╚═╝ ╚══════╝ ╚═╝    ╚══════╝ ╚══════╝ ╚═╝  ╚═╝

Options:
  --log-level [DEBUG|INFO|WARNING|ERROR]
                                  Log level.  [default: INFO]
  --db-url TEXT                   Database URL.
  --help                          Show this message and exit.

Commands:
  compare-wafers  Compare wafers
  db              Set of commands to manage related database
  parse           Parse files with measurements and save to database
  show            Show data from database
  summary         Group of command to analyze and summaryze the data
```
