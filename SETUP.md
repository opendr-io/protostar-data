# Protostar Installation

1. [Prerequisite Installations (Go, Node.js, Neo4j)](#prerequisite-installations)
2. [Set Up the Database and Upload Data](#upload-data-to-the-database)
3. [Set Up and Run the Web Application](#set-up-and-run-the-web-application)

---

## Prerequisite Installations

Ensure you have both the `protostar-data` and `protostar-web` repositories downloaded.

### Install Go

#### Linux

- Install Go
  ```bash
  sudo apt update
  sudo apt install golang-go
  ```

- Verify the installation

  ```
  go version
  ```

#### macOS

- Visit the [Go downloads page](https://golang.org/dl/).
- Download the macOS `.pkg` installer for the latest version.
- Open the `.pkg` file and follow the installation instructions.


### Install Neo4j

#### macOS

- Visit the [Neo4j download page](https://neo4j.com/download/).
- Download the macOS `.dmg` installer for the latest version.
- Open the `.dmg` file and drag the Neo4j icon to the Applications folder.
- Open Neo4j from the Applications folder and follow the setup instructions.

#### Linux

- Update package list and install Neo4j

  ```bash
  curl -fsSL https://debian.neo4j.com/neotechnology.gpg.key | sudo gpg --dearmor -o /usr/share/keyrings/neo4j.gpg
  echo "deb [signed-by=/usr/share/keyrings/neo4j.gpg] https://debian.neo4j.com stable latest" | sudo tee /etc/apt/sources.list.d/neo4j.list > /dev/null
  sudo apt update
  sudo apt install neo4j
  ```

- Start Neo4j

  ```bash
  sudo systemctl start neo4j
  sudo systemctl enable neo4j
  ```

## Upload Data to the Database

### Linux

- Begin and configure the database

  ```bash
  sudo systemctl enable neo4j
  sudo neo4j-admin set-initial-password $PASSWORD
  sudo systemctl start neo4j
  ```

- Navigate to the `protostar-data` directory.

- Run the following commands, passing your database password:

  ```bash
  go mod tidy
  go run main.go -password $PASSWORD
  ```

  The connection is configurable via flags, environment variables, or a `.env` file in the repository root (precedence: flags, then environment, then `.env`). Copy `.env.example` to `.env` and fill in your values; `.env` is git-ignored so credentials stay out of the repository. Defaults target a local install:

  | Flag         | Environment variable | Default                 |
  |--------------|----------------------|-------------------------|
  | `-uri`       | `NEO4J_URI`          | `bolt://localhost:7687` |
  | `-username`  | `NEO4J_USERNAME`     | `neo4j`                 |
  | `-password`  | `NEO4J_PASSWORD`     | `password`              |
  | `-data`      | —                    | `data`                  |
  | `-reset`     | —                    | `false`                 |

  Pass `-reset` to delete the existing graph before importing; by default new data is imported on top of it.

  Encryption follows the URI scheme: `bolt://` and `neo4j://` are unencrypted, `bolt+s://` and `neo4j+s://` use TLS. For Neo4j Aura use the `neo4j+s://...` URI shown in the Aura console.

### macOS

- Open Neo4j Desktop
- Start a new project
- Add a local DBMS with the name "neo4j" and your password
- Start the database

## Set Up and Run the Web Application

### Linux and macOS

- Navigate to the `protostar-web` directory (in terminal for macOS)

- Add a new .env file

  ```bash
  nano .env
  ```

- Add the following environment variables to the .env file

  ```bash
  REACT_APP_USERNAME="neo4j"
  REACT_APP_PASSWORD=$PASSWORD
  REACT_APP_DB_URL="http://localhost:7474/db/neo4j"
  ```

- Press Ctrl + O to save the file, then press Enter to confirm. Press Ctrl + X to exit nano.

