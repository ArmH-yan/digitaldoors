"""Main entry point for the lead generation scraper."""

import asyncio
import argparse
import sys
from src.pipeline import LeadGenerationPipeline, main


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Lead Generation Scraper for Armenian Construction Companies"
    )
    parser.add_argument(
        "-c", "--config",
        default="config.yaml",
        help="Path to configuration file (default: config.yaml)"
    )
    parser.add_argument(
        "--phase",
        choices=["all", "crawl", "enrich", "score", "store", "export"],
        default="all",
        help="Run specific pipeline phase (default: all)"
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging level (default: INFO)"
    )
    return parser.parse_args()


async def run_pipeline(args):
    """Run the pipeline with specified arguments."""
    pipeline = LeadGenerationPipeline(config_path=args.config)
    
    if args.phase == "all":
        await pipeline.run()
    else:
        # Run specific phase
        await pipeline.db.connect()
        
        if args.phase == "crawl":
            await pipeline._phase1_crawl()
        elif args.phase == "enrich":
            companies = await pipeline.db.get_all_companies()
            await pipeline._phase2_enrich(companies)
        elif args.phase == "score":
            companies = await pipeline.db.get_all_companies()
            await pipeline._phase3_score(companies)
        elif args.phase == "store":
            companies = await pipeline.db.get_all_companies()
            await pipeline._phase4_store(companies)
        elif args.phase == "export":
            companies = await pipeline.db.get_all_companies()
            await pipeline._phase5_export(companies)
        
        await pipeline.db.disconnect()


def main_sync():
    """Synchronous entry point."""
    args = parse_args()
    
    try:
        asyncio.run(run_pipeline(args))
    except KeyboardInterrupt:
        print("\nPipeline interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main_sync()
