"use client";

// Generic demo page: renders demo-config.js. It shows business information
// only; technical details stay in the server log unless technicalView is true.
import { useState } from "react";
import { demo } from "./demo-config";

function readPath(data, path) {
  if (!path) return undefined;
  return path.split(".").reduce((value, key) => (value == null ? value : value[key]), data);
}

function formatValue(value) {
  if (value === null || value === undefined || value === "") return "—";
  if (typeof value === "boolean") return value ? "✓" : "✗";
  if (typeof value === "number") return value.toLocaleString(demo.language);
  return String(value);
}

function initialValues() {
  return Object.fromEntries(demo.input.fields.map((field) => [field.name, ""]));
}

function InputField({ field, value, onChange }) {
  const common = {
    id: field.name,
    name: field.name,
    value,
    required: field.required,
    placeholder: field.placeholder,
    maxLength: field.maxLength,
    onChange: (event) => onChange(field.name, event.target.value),
  };
  if (field.type === "textarea") return <textarea rows={4} {...common} />;
  if (field.type === "select") {
    return (
      <select {...common}>
        <option value="">{field.placeholder || ""}</option>
        {(field.options || []).map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    );
  }
  return <input type={field.type === "number" ? "number" : "text"} {...common} />;
}

function ResultField({ field, data }) {
  const value = readPath(data, field.path);
  if (field.type === "list") {
    const rows = Array.isArray(value) ? value : [];
    if (rows.length === 0) return null;
    return (
      <div className="result-list">
        <h3>{field.label}</h3>
        <table>
          <thead>
            <tr>
              {field.columns.map((column) => (
                <th key={column.path}>{column.label}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, index) => (
              <tr key={index}>
                {field.columns.map((column) => (
                  <td key={column.path}>{formatValue(readPath(row, column.path))}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }
  if (value === undefined || value === null || value === "") return null;
  return (
    <div className="result-field">
      <span className="label">{field.label}</span>
      <span className="value">{formatValue(value)}</span>
    </div>
  );
}

function Result({ answer }) {
  if (answer.kind === "unavailable" || answer.kind === "invalid") {
    return (
      <section className="card notice warning">
        <p>{answer.kind === "invalid" ? demo.messages.invalid : demo.messages.unavailable}</p>
      </section>
    );
  }
  const data = answer.data || {};
  const outcomeValue = readPath(data, demo.result.outcome?.path);
  const outcome = demo.result.outcome?.values?.[outcomeValue];
  const message = readPath(data, demo.result.message?.path);
  const fallback = answer.kind === "rejected" ? demo.messages.rejected : null;
  return (
    <section className="card result">
      {outcome && <div className={`outcome ${outcome.tone || "info"}`}>{outcome.label}</div>}
      {(message || fallback) && <p className="message">{message || fallback}</p>}
      <div className="result-fields">
        {demo.result.fields.map((field) => (
          <ResultField key={field.path} field={field} data={data} />
        ))}
      </div>
      {demo.technicalView && (
        <details className="technical">
          <summary>Technical details</summary>
          <pre>{JSON.stringify(data, null, 2)}</pre>
        </details>
      )}
    </section>
  );
}

export default function Page() {
  const [values, setValues] = useState(initialValues);
  const [answer, setAnswer] = useState(null);
  const [working, setWorking] = useState(false);

  const update = (name, value) => setValues((current) => ({ ...current, [name]: value }));

  async function submit(event) {
    event.preventDefault();
    setWorking(true);
    setAnswer(null);
    const payload = Object.fromEntries(
      demo.input.fields.map((field) => [
        field.name,
        field.type === "number" && values[field.name] !== "" ? Number(values[field.name]) : values[field.name],
      ]),
    );
    try {
      const response = await fetch("/api/agent", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      setAnswer(await response.json());
    } catch {
      setAnswer({ kind: "unavailable" });
    } finally {
      setWorking(false);
    }
  }

  return (
    <main>
      <header className="hero">
        <h1>{demo.title}</h1>
        <p>{demo.story}</p>
      </header>
      <section className="card">
        <form onSubmit={submit}>
          {demo.input.fields.map((field) => (
            <label key={field.name} htmlFor={field.name}>
              <span>{field.label}</span>
              <InputField field={field} value={values[field.name]} onChange={update} />
            </label>
          ))}
          {demo.input.examples?.length > 0 && (
            <div className="examples">
              {demo.input.examples.map((example) => (
                <button
                  type="button"
                  key={example.label}
                  className="example"
                  onClick={() => setValues({ ...initialValues(), ...example.values })}
                >
                  {example.label}
                </button>
              ))}
            </div>
          )}
          <button type="submit" className="primary" disabled={working}>
            {working ? demo.messages.working : demo.input.submitLabel}
          </button>
        </form>
      </section>
      {answer && <Result answer={answer} />}
    </main>
  );
}
