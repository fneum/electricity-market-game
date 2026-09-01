
# Goals

Create an online interactive game to simulate a simple electricity market merit order for teaching purposes.

# Context

- This game is played as part of a university course on energy economics. 
- It is played before any theory is explained (building intuition)
- The tool should be didactically suitable and accessible and not overloaded.
- The game is played with varying student numbers; role descriptions must scale automatically based on number of teams in a sensible way (e.g. splitting capacity, slightly altering constraints).
- `Roleplay_electricity_market.tex` includes the instructions how this game is currently played on paper (the scenarios are well-tested, but for fixed number of teams); read it first to understand the general gameplay
- The students should experience competitive pressure, strategic adaptation, learning dynamics.

# Development Instructions

- UI: simple minimialistic, yet modern looking and visually appealing, using standard tools
- no logins, working with game links and team names only
- Python preferred with uv
- use test-driven development with pytest for backend
- catch edge-gases (e.g. bid sitting between two clearing prices)
- cleanly separate UI, server, simulation backend
- check validity of submitted bids (and notify student team)
- I really liked the technical setup of this `doppelkopf` project (take it as inspiration)
- Include instructions in a README how to deploy the game.
- Use `ruff` and `mypy`, but leniently.
- Try to write simple code that is still easy to understand; limit volume.

# Gameplay

- Two types of users: 1) lecturer who sets up game, starts and closes rounds 2) student teams (e.g. groups of 2-3) who submit bids based on their roles each round.
- The student teams compete for who achieves the highest profit (it's not a fair game, and not intended to!)
- The student teams get randomly assigned technology (from a selection, with described costs and various technical constraints)
- The lecturer gets an admin view to control scenarios and rounds and to display market clearing results (e.g. on a projector).
- The game is played in multiple rounds (with different specific conditions, e.g. demand, renewables, gas price shock, co2 price, etc.)
- Each round consists of multiple views for the student teams: A) interface to submit bids privately (without knowledge of others) and B) display of market clearing result
- A) should also describe technology role and constraints for the current round; bids can also be split (e.g. 100 €/MWh for first 100MW, 150 €/MWh for 200MW)
- B) should include the cohort leaderboard; the merit order for the current round and how it cleared (volume & price & (emissions)); the group's own profit calculation (didactically presented)
- Normally, 4 rounds are paid, but it should be configurable by the lecturer.
- Are batteries potentially another technology worth including? (not a priority)
