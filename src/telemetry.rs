use anyhow::Result;
use tracing_subscriber::{layer::SubscriberExt, util::SubscriberInitExt, EnvFilter};

pub struct Telemetry;

impl Telemetry {
    pub fn init() -> Result<()> {
        let env_filter = EnvFilter::try_from_default_env()
            .unwrap_or_else(|_| EnvFilter::new("info"));
        
        let fmt_layer = tracing_subscriber::fmt::layer()
            .with_target(true)
            .with_thread_ids(true)
            .with_line_number(true)
            .compact();
        
        tracing_subscriber::registry()
            .with(env_filter)
            .with(fmt_layer)
            .init();
        
        Ok(())
    }
}
