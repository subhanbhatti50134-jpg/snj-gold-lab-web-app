import { Component, type ErrorInfo, type ReactNode } from "react";

interface Props {
  children: ReactNode;
}

interface State {
  error: Error | null;
}

/**
 * Keeps a single crashing component from taking the whole app down to a
 * blank page: shows a recovery screen instead and logs the error to the
 * console for support.
 */
export default class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("SNJ Gold Lab UI crashed:", error, info.componentStack);
  }

  render() {
    if (this.state.error) {
      return (
        <div
          style={{
            minHeight: "100vh",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            padding: 24,
            background: "#f4f6fa",
            fontFamily: "system-ui, sans-serif"
          }}
        >
          <div
            style={{
              background: "#fff",
              border: "1px solid #e7ecf2",
              borderRadius: 10,
              padding: "28px 32px",
              maxWidth: 460,
              textAlign: "center"
            }}
          >
            <h1 style={{ fontSize: 18, margin: "0 0 8px", color: "#142438" }}>
              SNJ Gold Lab
            </h1>
            <p style={{ fontSize: 13, color: "#66768b", margin: "0 0 18px" }}>
              Kuch ghalat ho gaya. Page dobara load karein — agar masla dobara
              aaye to admin ko batayein.
            </p>
            <button
              type="button"
              onClick={() => window.location.reload()}
              style={{
                padding: "8px 18px",
                borderRadius: 6,
                border: "none",
                background: "#1d4ed8",
                color: "#fff",
                fontSize: 13,
                cursor: "pointer"
              }}
            >
              Page dobara load karein
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
