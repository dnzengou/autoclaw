use autoclaw::agent::{AgentConfig, AgentLoop};
use autoclaw::eval::EvalEngine;
use autoclaw::server::APIServer;
use autoclaw::telemetry::Telemetry;
use clap::Parser;
use tracing::info;

#[derive(Parser, Debug)]
#[command(name = "autoclaw")]
#[command(about = "No-code self-improving automation loop")]
struct Cli {
    #[command(subcommand)]
    command: Commands,
}

#[derive(clap::Subcommand, Debug)]
enum Commands {
    /// Initialize new autoclaw project
    Init {
        #[arg(default_value = ".")]
        path: String,
    },
    /// Start agent loop
    Run {
        #[arg(short, long, default_value = "context.md")]
        context: String,
        #[arg(short, long, default_value = "300")]
        budget_seconds: u64,
        #[arg(short, long)]
        headless: bool,
    },
    /// Evaluate single run
    Eval {
        #[arg(short, long)]
        run_id: String,
    },
    /// Start API server
    Server {
        #[arg(short, long, default_value = "8080")]
        port: u16,
    },
    /// Deploy to production
    Deploy {
        #[arg(short, long, default_value = "fly")]
        target: String,
    },
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    Telemetry::init()?;

    let cli = Cli::parse();

    match cli.command {
        Commands::Init { path } => {
            info!("Initializing autoclaw project at {}", path);
            autoclaw::init::create_project(&path).await?;
        }
        Commands::Run {
            context,
            budget_seconds,
            headless,
        } => {
            info!("Starting agent loop with {}s budget", budget_seconds);
            let config = AgentConfig {
                context_path: context,
                budget_seconds,
                headless,
                ..Default::default()
            };
            let agent = AgentLoop::new(config).await?;
            agent.run().await?;
        }
        Commands::Eval { run_id } => {
            info!("Evaluating run {}", run_id);
            let eval_engine = EvalEngine::new().await?;
            let result = eval_engine.evaluate(&run_id).await?;
            println!("{}", serde_json::to_string_pretty(&result)?);
        }
        Commands::Server { port } => {
            info!("Starting API server on port {}", port);
            let server = APIServer::new(port).await?;
            server.run().await?;
        }
        Commands::Deploy { target } => {
            info!("Deploying to {}", target);
            autoclaw::deploy::deploy(&target).await?;
        }
    }

    Ok(())
}
