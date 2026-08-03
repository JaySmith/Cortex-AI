# Cortex Hub Knowledge Model

A shared knowledge hub where agents store and retrieve information, with priority based on areas of interest rather than fixed roles.

## Language

**Agent**:
A persona (human + AI pair) that interacts with the hub. Each agent has a profile of interests that influence knowledge retrieval.
_Avoid_: User, client

**Knowledge Entry**:
A discrete piece of information stored in the hub — a learning, a resolution, a pattern, a reference.
_Avoid_: Memory, fact, record

**Interest**:
A declared area an agent cares about. Agents can have multiple interests, ordered by priority.
_Avoid_: Role, tag, skill, domain

**Interest Profile**:
The ordered list of interests belonging to an agent. The hub uses this to prioritize which knowledge entries surface first.
_Avoid_: Role list, tag cloud

**Interest Registry**:
An emergent set of interest values, weighted by adoption. No central gatekeeper — interests with more agents and knowledge entries naturally carry more signal. Solves noise pollution without a governance bottleneck.
_Avoid_: Role registry, tag namespace

**Interest Flag**:
An explicit mention of an interest name by the user that signals the hub to boost knowledge entries under that interest. Without a flag, the hub performs a general search across all interests.
_Avoid_: Trigger, tag mention

**Hub Vault**:
A shared Postgres-backed knowledge store that holds all knowledge entries, their link graph, and the agent interest registry. The source of truth for shared knowledge.
_Avoid_: Remote vault, cloud vault

**Ingestion Pipeline**:
The process by which a user-pushed local note is parsed, tagged, linked against existing entries, and inserted into the hub vault's link graph.
_Avoid_: Sync, import
