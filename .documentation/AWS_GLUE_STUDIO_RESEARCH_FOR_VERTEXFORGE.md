# AWS Glue Studio Research for VertexForge

> Project: VertexForge
> Date: 2026-05-12
> Purpose: Study AWS Glue Studio's visual ETL authoring model and identify patterns that can inform VertexForge's future DSL and UI builder.

## Research Sources

Primary AWS documentation used:

- [AWS Glue components](https://docs.aws.amazon.com/glue/latest/dg/components-overview.html)
- [Job editor features](https://docs.aws.amazon.com/glue/latest/dg/job-editor-features.html)
- [Building visual ETL jobs](https://docs.aws.amazon.com/glue/latest/dg/author-job-glue.html)
- [Transform data with AWS Glue managed transforms](https://docs.aws.amazon.com/glue/latest/dg/edit-jobs-transforms.html)
- [Transform data with custom visual transforms](https://docs.aws.amazon.com/glue/latest/dg/custom-visual-transform.html)
- [Custom visual transform JSON config](https://docs.aws.amazon.com/glue/latest/dg/custom-visual-transform-json-config-file.html)
- [Custom visual transform validation](https://docs.aws.amazon.com/glue/latest/dg/custom-visual-transform-validation.html)

## Executive Takeaway

AWS Glue Studio is useful inspiration because it treats the UI as an authoring surface over a real executable representation.

Users arrange sources, transforms, and targets visually. AWS Glue generates executable ETL code from that visual graph. The visual editor is not the core runtime. The core remains the job definition, generated script, data catalog, transforms, and Spark execution environment.

That maps well to VertexForge:

- Visual graph later.
- JSON DSL now.
- Compiler/runtime as the real product.
- UI as an authoring shell over stable node definitions.

## What AWS Glue Studio Does

AWS Glue Studio provides a visual interface for creating ETL jobs. A visual job is a graph of nodes:

- Data source nodes.
- Transform nodes.
- Data target nodes.

The visual editor lets users configure each node, preview output schema/data, and generate or view the underlying job script. AWS Glue then runs the job on its managed Spark/Ray infrastructure.

Important Glue idea:

The visual graph has an executable backend. It is not just a diagram.

## Visual Model

AWS Glue's job editor has several concepts that map cleanly to VertexForge.

### Canvas

Glue has a visual canvas where users add, remove, connect, and arrange nodes. It supports layout direction, zoom, recenter, undo/redo, and node deletion.

VertexForge equivalent:

- Later UI can show workflow nodes and edges.
- The canvas should generate JSON DSL, not runtime behavior directly.
- The canvas should be optional until the DSL is stable.

### Resource Panel

Glue has a searchable resource panel with transforms and data nodes. Nodes are organized into categories like transforms, sources, and targets.

VertexForge equivalent:

- Node palette should be generated from a node registry.
- Node registry should include LLM, source, transform, validator, router, map, and subgraph nodes.
- Each node definition should include parameter schema, display name, description, input/output contract, and validation rules.

### Properties Panel

Glue opens a properties panel when a node is selected. This is where node configuration happens.

VertexForge equivalent:

- A future UI should not hardcode every node form.
- The form should be generated from the node type's parameter schema.
- This is directly parallel to Glue custom visual transform JSON configs.

### Data Preview and Output Schema

Glue lets users inspect sample data and output schema for selected nodes before running the full job.

VertexForge equivalent:

- We should eventually support "node preview" or "dry run on sample input."
- For LLM nodes, preview could run a single node against current state.
- For transform/validator nodes, preview can be deterministic and fast.
- For source loaders, preview is already close to the artifact view we built.

## Script Generation Pattern

AWS Glue Studio can generate an executable job script from the visual representation. Users can view or edit the script. AWS documentation notes that editing the script can convert the job into script-only mode, after which the visual editor is no longer the editing surface.

This is a strong pattern for VertexForge:

- JSON DSL should be the canonical representation.
- A future UI can generate JSON.
- Advanced users can edit JSON directly.
- If direct JSON edits use unsupported UI features, the UI can still render a read-only or advanced mode.

Potential rule:

If a workflow uses DSL constructs unsupported by the visual builder, keep the JSON executable and show a limited visual preview rather than blocking execution.

## Schema and Data Catalog Pattern

AWS Glue uses the Data Catalog as a metadata store for data sources, schemas, and related control information. Crawlers can infer schemas and store them for ETL jobs.

VertexForge equivalent:

- Source artifacts are our early "catalog."
- We should separate uploaded source metadata from workflow state.
- Future catalog records should include source schemas, artifact schemas, and node output schemas.
- DSL compilation should validate references against known schemas where possible.

Useful idea:

Treat artifact metadata and state schemas as first-class catalog items, not random blobs.

## Transform Node Model

AWS Glue has built-in transforms and custom visual transforms.

Managed transforms operate on a data structure called a `DynamicFrame`, which extends Spark DataFrame behavior. The key idea is that every transform has a known input/output data structure, and downstream nodes consume that structure.

VertexForge equivalent:

- Our equivalent of `DynamicFrame` is the graph state plus typed artifacts.
- Every node should declare:
  - input state keys
  - output state key
  - output schema
  - side effects, if any
- Transform and validator nodes should be just as first-class as LLM nodes.

## Custom Visual Transform Pattern

Glue custom visual transforms are particularly relevant.

AWS uses:

- A Python file containing transform logic.
- A JSON config file describing the transform.
- Optional icon.
- Parameter definitions.
- Validation rules.
- UI rendering hints.
- Upload/discovery from a known location.

This maps almost perfectly to a future VertexForge node plugin model.

VertexForge node package could look like:

```text
nodes/
  invoice_total_validator/
    node.json
    node.py
    icon.svg
```

Example `node.json` shape:

```json
{
  "name": "invoice_total_validator",
  "display_name": "Invoice Total Validator",
  "description": "Checks subtotal, tax, shipping, discounts, and final total.",
  "type": "validator",
  "function_name": "validate_invoice_totals",
  "input_schema": "InvoiceExtractionResult",
  "output_schema": "ValidationResult",
  "parameters": [
    {
      "name": "tolerance",
      "type": "float",
      "default": 0.01,
      "description": "Allowed difference for currency reconciliation."
    }
  ]
}
```

Important borrowed idea:

Node implementation and node UI metadata should be paired but separate.

## Parameter Schema Pattern

Glue custom transform JSON supports:

- `name`
- `displayName`
- `description`
- `functionName`
- `path`
- `parameters`
- parameter types
- optional fields
- regex validation
- list options
- column selectors based on parent output schema

VertexForge should borrow this heavily.

Future node parameter schema should support:

- strings, numbers, booleans, lists, enums
- required/optional fields
- validation rules
- defaults
- secret/environment references
- model selectors
- prompt selectors
- artifact selectors
- state key selectors
- schema-field selectors

Especially useful:

Glue can populate parameter options from the parent node output schema. VertexForge can do the same with state fields and artifact schemas.

## Preview Session Pattern

Glue preview sessions let users inspect node output without running the full job. AWS documentation calls out that preview sessions can use sampled data and can update output schema from preview results.

VertexForge equivalent:

- `preview_node(workflow_json, node_id, sample_state)`
- `infer_output_schema(node_id, sample_state)`
- `run_until_node(workflow_json, node_id)`
- `dry_run_validator(node_id, sample_payload)`

This should come after the core runtime is strong. But it should be considered while designing node contracts.

## Validation Pattern

Glue validates custom visual transform JSON before loading it into the visual editor. Validation includes required fields, JSON format, invalid parameters, matching Python and JSON files, and file pairing.

VertexForge equivalent:

- Validate node plugin manifests before loading them.
- Validate JSON workflows before execution.
- Validate state field references.
- Validate node input/output contracts.
- Validate available node types.
- Validate plugin implementation exists.

This supports our current direction: strict compile-time validation should be a core feature, not UI-only logic.

## Code Editing Boundary

Glue lets users move from visual authoring to code editing, but there is a boundary: once the generated script is edited, the visual job can become script-only.

VertexForge should define a similar boundary:

- Simple workflows can be fully visual.
- Advanced workflows may be JSON-first.
- UI should never flatten or silently rewrite unsupported advanced DSL features.
- The visual builder can display "advanced JSON mode" for constructs it cannot edit.

## Ideas To Borrow Directly

1. Node registry as a searchable palette.
2. Node config generated from manifest parameters.
3. First-class source, transform, and target categories.
4. Output schema preview per node.
5. Sample data preview per node.
6. Generated executable representation from visual graph.
7. Custom node/plugin manifest paired with implementation code.
8. Browser-side validation for form parameters plus compiler-side validation.
9. Versioned node definitions.
10. Clear boundary between visual editing and advanced code/JSON editing.

## Ideas To Avoid For Now

1. Heavy visual canvas before the DSL is stable.
2. Custom observability UI while Phoenix already covers traces.
3. Building a data catalog UI before artifact/state schemas settle.
4. Treating visual layout as part of execution semantics.
5. Generating Python code too early if JSON-to-LangGraph compilation remains more direct.

## VertexForge Design Translation

AWS Glue concept to VertexForge concept:

| AWS Glue Studio | VertexForge |
|---|---|
| Visual ETL job | JSON agentic workflow |
| Data source node | Source loader/artifact node |
| Transform node | LLM, transform, validator, router, map, subgraph node |
| Data target node | Final output, report writer, artifact writer |
| DynamicFrame | Typed state field or artifact payload |
| Data Catalog | Source/artifact/state schema catalog |
| Custom visual transform JSON | Node plugin manifest |
| Transform Python file | Node implementation |
| Output schema tab | Node output schema preview |
| Data preview tab | Node dry run / sample execution |
| Script tab | JSON DSL view or generated Python view |
| Runs tab | Phoenix trace links plus run metadata |

## Recommended VertexForge Path

### Phase 1: Core Runtime

- CLI runner.
- Examples folder.
- State-backed linear workflows.
- Strong tests.
- Phoenix traces.

### Phase 2: Node Registry

- Built-in node manifests.
- Node implementation registry.
- Parameter validation.
- Node categories.

### Phase 3: Non-LLM Nodes

- Transform node.
- Validator node.
- Source/artifact read node.
- Output writer node.

### Phase 4: Workflow Control

- Router node.
- Conditional edges.
- Map/fan-out node.
- Subgraph node.

### Phase 5: UI Builder

- Node palette from registry.
- Properties panel from manifest.
- JSON view.
- Node output schema preview.
- Thin Phoenix run links.

## Practical Insight

Glue did not start from "make a pretty graph." It has a runtime model:

- sources
- transforms
- targets
- schemas
- generated executable code
- preview
- validation

VertexForge should follow the same order:

1. Runtime model.
2. Node contracts.
3. DSL validation.
4. Execution.
5. Preview.
6. UI builder.

That order keeps the UI honest. The UI should expose capability that exists in the compiler, not invent capability that the compiler cannot actually run.

