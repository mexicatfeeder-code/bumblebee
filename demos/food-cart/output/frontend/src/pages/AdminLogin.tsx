/**
 * Admin Login Page
 *
 * Provides a PIN-based authentication form for admin access.
 * Validates the entered PIN against the backend settings API.
 * On success, navigates to the admin panel. On failure, displays an error message.
 */

import { useState, FormEvent, ChangeEvent } from "react";
import { useNavigate } from "react-router-dom";
import "../styles/design-tokens.css";

interface AdminLoginResponse {
  success: boolean;
  message?: string;
}

interface AdminLoginError {
  error: string;
}

const AdminLogin = () => {
  const navigate = useNavigate();
  const [pin, setPin] = useState<string>("");
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string>("");
  const [attempts, setAttempts] = useState<number>(0);

  const MAX_ATTEMPTS = 5;
  const LOCKOUT_DURATION = 30000; // 30 seconds

  const handlePinChange = (e: ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value.replace(/\D/g, "");
    if (value.length <= 20) {
      setPin(value);
      setError("");
    }
  };

  const handleSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();

    if (!pin.trim()) {
      setError("Please enter your admin PIN.");
      return;
    }

    if (pin.length < 4) {
      setError("PIN must be at least 4 characters long.");
      return;
    }

    setIsLoading(true);
    setError("");

    try {
      const response = await fetch("/api/settings/admin/login", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ pin }),
      });

      const data: AdminLoginResponse | AdminLoginError = await response.json();

      if (response.ok && (data as AdminLoginResponse).success) {
        // Store auth state in session storage
        sessionStorage.setItem("adminAuthenticated", "true");
        sessionStorage.setItem("adminLoginTime", Date.now().toString());
        navigate("/admin");
      } else {
        const newAttempts = attempts + 1;
        setAttempts(newAttempts);

        if (newAttempts >= MAX_ATTEMPTS) {
          setError(
            `Too many failed attempts. Please wait ${LOCKOUT_DURATION / 1000} seconds before trying again.`
          );
          setPin("");
          // Disable form temporarily
          setTimeout(() => {
            setAttempts(0);
            setError("");
          }, LOCKOUT_DURATION);
        } else {
          setError(
            (data as AdminLoginError).error ||
              "Invalid PIN. Please try again."
          );
          setPin("");
        }
      }
    } catch {
      setError("Network error. Please check your connection and try again.");
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      handleSubmit(e as unknown as FormEvent<HTMLFormElement>);
    }
  };

  return (
    <div className="admin-login-page">
      <div className="admin-login-container">
        <div className="admin-login-card">
          <div className="admin-login-header">
            <div className="admin-login-icon">🔒</div>
            <h1 className="admin-login-title">Admin Login</h1>
            <p className="admin-login-subtitle">
              Enter your PIN to access the admin panel
            </p>
          </div>

          <form onSubmit={handleSubmit} className="admin-login-form" noValidate>
            <div className="admin-login-field">
              <label htmlFor="admin-pin" className="admin-login-label">
                Admin PIN
              </label>
              <input
                id="admin-pin"
                type="password"
                inputMode="numeric"
                pattern="[0-9]*"
                value={pin}
                onChange={handlePinChange}
                onKeyDown={handleKeyDown}
                placeholder="Enter your PIN"
                autoComplete="one-time-code"
                disabled={isLoading || attempts >= MAX_ATTEMPTS}
                className="admin-login-input"
                aria-describedby={error ? "admin-login-error" : undefined}
                aria-invalid={!!error}
                autoFocus
              />
            </div>

            {error && (
              <div
                id="admin-login-error"
                className="admin-login-error"
                role="alert"
              >
                <span className="admin-login-error-icon">⚠️</span>
                <span className="admin-login-error-text">{error}</span>
              </div>
            )}

            {attempts > 0 && attempts < MAX_ATTEMPTS && (
              <div className="admin-login-attempts">
                {MAX_ATTEMPTS - attempts} attempt
                {MAX_ATTEMPTS - attempts !== 1 ? "s" : ""} remaining
              </div>
            )}

            <button
              type="submit"
              className="admin-login-submit"
              disabled={isLoading || attempts >= MAX_ATTEMPTS}
            >
              {isLoading ? (
                <span className="admin-login-loading">
                  <span className="admin-login-spinner" />
                  Verifying...
                </span>
              ) : (
                "Submit"
              )}
            </button>
          </form>

          <div className="admin-login-footer">
            <p className="admin-login-hint">
              Forgot your PIN? Contact the system administrator.
            </p>
          </div>
        </div>
      </div>

      <style>{`
        .admin-login-page {
          display: flex;
          align-items: center;
          justify-content: center;
          min-height: 100vh;
          background-color: var(--bg-page);
          padding: var(--spacing-lg);
        }

        .admin-login-container {
          width: 100%;
          max-width: 420px;
        }

        .admin-login-card {
          background-color: var(--bg-card);
          border-radius: var(--radius-lg);
          padding: var(--spacing-xl);
          box-shadow: var(--shadow-md);
          border: 1px solid var(--border-color);
        }

        .admin-login-header {
          text-align: center;
          margin-bottom: var(--spacing-xl);
        }

        .admin-login-icon {
          font-size: 3rem;
          margin-bottom: var(--spacing-md);
        }

        .admin-login-title {
          font-size: var(--font-size-xl);
          font-weight: var(--font-weight-bold);
          color: var(--text-primary);
          margin: 0 0 var(--spacing-sm) 0;
        }

        .admin-login-subtitle {
          font-size: var(--font-size-sm);
          color: var(--text-secondary);
          margin: 0;
        }

        .admin-login-form {
          display: flex;
          flex-direction: column;
          gap: var(--spacing-md);
        }

        .admin-login-field {
          display: flex;
          flex-direction: column;
          gap: var(--spacing-xs);
        }

        .admin-login-label {
          font-size: var(--font-size-sm);
          font-weight: var(--font-weight-medium);
          color: var(--text-primary);
        }

        .admin-login-input {
          padding: var(--spacing-md);
          font-size: var(--font-size-lg);
          font-family: var(--font-family-mono);
          letter-spacing: 0.25em;
          text-align: center;
          border: 2px solid var(--border-color);
          border-radius: var(--radius-md);
          background-color: var(--bg-input);
          color: var(--text-primary);
          transition: border-color var(--transition-fast),
                      box-shadow var(--transition-fast);
          outline: none;
        }

        .admin-login-input:focus {
          border-color: var(--color-primary);
          box-shadow: 0 0 0 3px var(--color-primary-alpha);
        }

        .admin-login-input:disabled {
          opacity: 0.6;
          cursor: not-allowed;
        }

        .admin-login-input::placeholder {
          color: var(--text-muted);
          letter-spacing: 0;
          font-family: var(--font-family-sans);
        }

        .admin-login-error {
          display: flex;
          align-items: center;
          gap: var(--spacing-sm);
          padding: var(--spacing-sm) var(--spacing-md);
          background-color: var(--bg-error);
          border: 1px solid var(--border-error);
          border-radius: var(--radius-md);
          animation: admin-login-shake 0.3s ease-in-out;
        }

        .admin-login-error-icon {
          font-size: 1rem;
        }

        .admin-login-error-text {
          font-size: var(--font-size-sm);
          color: var(--text-error);
        }

        .admin-login-attempts {
          font-size: var(--font-size-xs);
          color: var(--text-warning);
          text-align: center;
        }

        .admin-login-submit {
          padding: var(--spacing-md) var(--spacing-lg);
          font-size: var(--font-size-md);
          font-weight: var(--font-weight-semibold);
          color: var(--text-inverse);
          background-color: var(--color-primary);
          border: none;
          border-radius: var(--radius-md);
          cursor: pointer;
          transition: background-color var(--transition-fast),
                      opacity var(--transition-fast);
          margin-top: var(--spacing-sm);
        }

        .admin-login-submit:hover:not(:disabled) {
          background-color: var(--color-primary-hover);
        }

        .admin-login-submit:disabled {
          opacity: 0.6;
          cursor: not-allowed;
        }

        .admin-login-loading {
          display: inline-flex;
          align-items: center;
          gap: var(--spacing-sm);
        }

        .admin-login-spinner {
          display: inline-block;
          width: 16px;
          height: 16px;
          border: 2px solid var(--text-inverse);
          border-top-color: transparent;
          border-radius: 50%;
          animation: admin-login-spin 0.6s linear infinite;
        }

        .admin-login-footer {
          margin-top: var(--spacing-xl);
          text-align: center;
          border-top: 1px solid var(--border-color);
          padding-top: var(--spacing-lg);
        }

        .admin-login-hint {
          font-size: var(--font-size-xs);
          color: var(--text-muted);
          margin: 0;
        }

        @keyframes admin-login-shake {
          0%, 100% { transform: translateX(0); }
          20% { transform: translateX(-4px); }
          40% { transform: translateX(4px); }
          60% { transform: translateX(-4px); }
          80% { transform: translateX(4px); }
        }

        @keyframes admin-login-spin {
          to { transform: rotate(360deg); }
        }

        @media (max-width: 480px) {
          .admin-login-card {
            padding: var(--spacing-lg);
          }

          .admin-login-icon {
            font-size: 2.5rem;
          }

          .admin-login-title {
            font-size: var(--font-size-lg);
          }
        }
      `}</style>
    </div>
  );
};

export default AdminLogin;
