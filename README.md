# Compiler Crew

Welcome to the Compiler Crew project, powered by [crewAI](https://crewai.com). This template is designed to help you set up a multi-agent AI system with ease, leveraging the powerful and flexible framework provided by crewAI. Our goal is to enable your agents to collaborate effectively on complex tasks, maximizing their collective intelligence and capabilities.

## Installation

Ensure you have Python >=3.10 <3.14 installed on your system. This project uses [UV](https://docs.astral.sh/uv/) for dependency management and package handling, offering a seamless setup and execution experience.

First, if you haven't already, install uv:

```bash
pip install uv
```

Next, navigate to your project directory and install the dependencies:

(Optional) Lock the dependencies and install them by using the CLI command:
```bash
crewai install
```
### Customizing

**Add your `OPENAI_API_KEY` into the `.env` file**

- Modify `src/compiler/config/agents.yaml` to define your agents
- Modify `src/compiler/config/tasks.yaml` to define your tasks
- Modify `src/compiler/crew.py` to add your own logic, tools and specific args
- Modify `src/compiler/main.py` to add custom inputs for your agents and tasks

## Running the Project

To kickstart your crew of AI agents and begin task execution, run this from the root folder of your project:

```bash
$ crewai run
```

This command initializes the compiler Crew, assembling the agents and assigning them tasks as defined in your configuration.

This example, unmodified, will run the create a `report.md` file with the output of a research on LLMs in the root folder.

## Understanding Your Crew

The compiler Crew is composed of multiple AI agents, each with unique roles, goals, and tools. These agents collaborate on a series of tasks, defined in `config/tasks.yaml`, leveraging their collective skills to achieve complex objectives. The `config/agents.yaml` file outlines the capabilities and configurations of each agent in your crew.

## Evaluation Framework

ProtoFlow includes a manual, one-prompt-at-a-time evaluation framework that logs pipeline metrics (latency, token usage, repair loops, HITL triggers) and gathers human pass/fail judgments.

### Running Evaluations

1. Start the backend:
   ```bash
   uv run serve
   ```
2. Start the frontend:
   ```bash
   cd frontend
   npm run dev
   ```
3. Navigate to `http://localhost:5173/eval` to access the Evaluation Dashboard.

### Features
- **Summary Metrics**: Real-time pass rates, average token usage, average latency, and HITL trigger rates.
- **Interactive Visualizations**: Donut chart of pass/fail ratios, latencies by difficulty, and repair loops.
- **Bulk Runner**: Sequential automatic execution of all unrun test prompts.
- **Judgment Modal**: Ability to score runs, add qualitative notes, and categorize failures.

## Support

For support, questions, or feedback regarding the Compiler Crew or crewAI.
- Visit our [documentation](https://docs.crewai.com)
- Reach out to us through our [GitHub repository](https://github.com/joaomdmoura/crewai)
- [Join our Discord](https://discord.com/invite/X4JWnZnxPb)
- [Chat with our docs](https://chatg.pt/DWjSBZn)

Let's create wonders together with the power and simplicity of crewAI.
