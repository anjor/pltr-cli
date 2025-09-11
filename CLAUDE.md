## Development tips

The basis of the SDK is https://github.com/palantir/foundry-platform-python. Their main
branch is develop and not main.
This project is a CLI that wraps around the SDK to give a CLI interface.

## Python guidance

- ALWAYS Use uv for dependency management.
- ALWAYS Use uv to run python scripts.

## General Guidance

1. Be honest about what the SDK supports
2. Remove non-working commands rather than showing confusing errors
3. Focus on excellence in the features that do work
4. Provide clear guidance about the RID-based nature of the API
