import React, { useEffect, useRef, useState, useCallback } from 'react';
import '../styles/design-tokens.css';

export interface OrderStatus {
  orderId: string;
  status: 'pending' | 'preparing' | 'ready' | 'picked_up' | 'cancelled';
  updatedAt: string;
  message?: string;
}

interface OrderConfirmationProps {
  orderId: string;
  orderItems: Array<{
    menuItemId: string;
    menuItemName: string;
    quantity: number;
    unitPrice: number;
  }>;
  totalAmount: number;
  onReturnToMenu?: () => void;
}

const STATUS_LABELS: Record<string, string> = {
  pending: 'Pending',
  preparing: 'Preparing',
  ready: 'Ready for Pickup',
  picked_up: 'Picked Up',
  cancelled: 'Cancelled',
};

const STATUS_STEPS = ['pending', 'preparing', 'ready', 'picked_up'];

const OrderConfirmation: React.FC<OrderConfirmationProps> = ({
  orderId,
  orderItems,
  totalAmount,
  onReturnToMenu,
}) => {
  const [currentStatus, setCurrentStatus] = useState<string>('pending');
  const [statusHistory, setStatusHistory] = useState<OrderStatus[]>([]);
  const [isConnected, setIsConnected] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const getStatusIndex = useCallback(
    (status: string) => {
      return STATUS_STEPS.indexOf(status);
    },
    []
  );

  const isStatusComplete = useCallback(
    (status: string) => {
      const currentIndex = getStatusIndex(currentStatus);
      const stepIndex = getStatusIndex(status);
      return stepIndex <= currentIndex;
    },
    [currentStatus, getStatusIndex]
  );

  const connectWebSocket = useCallback(() => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/orders/${orderId}`;

    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      setIsConnected(true);
      setError(null);
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);

        if (data.type === 'connection_established') {
          setIsConnected(true);
          setError(null);
        } else if (data.type === 'status_update') {
          const newStatus: OrderStatus = {
            orderId: data.orderId || orderId,
            status: data.status,
            updatedAt: data.updatedAt || new Date().toISOString(),
            message: data.message,
          };

          setCurrentStatus(newStatus.status);
          setStatusHistory((prev) => [...prev, newStatus]);
        } else if (data.type === 'error') {
          setError(data.message || 'An error occurred');
        }
      } catch (err) {
        console.error('Failed to parse WebSocket message:', err);
      }
    };

    ws.onerror = () => {
      setError('Connection error. Attempting to reconnect...');
      setIsConnected(false);
    };

    ws.onclose = () => {
      setIsConnected(false);
      // Attempt to reconnect after 3 seconds
      reconnectTimeoutRef.current = setTimeout(() => {
        connectWebSocket();
      }, 3000);
    };
  }, [orderId]);

  useEffect(() => {
    connectWebSocket();

    return () => {
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
    };
  }, [connectWebSocket]);

  const handleReturnToMenu = useCallback(() => {
    if (onReturnToMenu) {
      onReturnToMenu();
    }
  }, [onReturnToMenu]);

  const formatTime = (isoString: string) => {
    try {
      const date = new Date(isoString);
      return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    } catch {
      return '';
    }
  };

  return (
    <div className="order-confirmation-page" role="main" aria-label="Order Confirmation">
      <div className="order-confirmation-card">
        <div className="order-confirmation-header">
          <div className="order-success-icon" aria-hidden="true">
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <circle cx="12" cy="12" r="10" />
              <path d="M9 12l2 2 4-4" />
            </svg>
          </div>
          <h1 className="order-confirmation-title">Order Confirmed!</h1>
          <p className="order-confirmation-subtitle">
            Your order has been received and is being processed.
          </p>
        </div>

        <div className="order-number-section">
          <span className="order-number-label">Order Number</span>
          <span className="order-number-value" data-testid="order-number">
            {orderId}
          </span>
        </div>

        <div className="order-status-tracker" aria-label="Order Status">
          <div className="status-connection-indicator">
            <span
              className={`connection-dot ${isConnected ? 'connected' : 'disconnected'}`}
              aria-hidden="true"
            />
            <span className="connection-text">
              {isConnected ? 'Live Updates Active' : 'Reconnecting...'}
            </span>
          </div>

          <div className="status-steps" role="progressbar" aria-valuenow={getStatusIndex(currentStatus)} aria-valuemin={0} aria-valuemax={STATUS_STEPS.length - 1}>
            {STATUS_STEPS.map((step, index) => {
              const isComplete = isStatusComplete(step);
              const isCurrent = currentStatus === step;
              return (
                <div key={step} className="status-step-wrapper">
                  <div
                    className={`status-step ${isComplete ? 'complete' : ''} ${isCurrent ? 'active' : ''}`}
                    aria-current={isCurrent ? 'step' : undefined}
                  >
                    <div className="status-step-circle">
                      {isComplete ? (
                        <svg
                          xmlns="http://www.w3.org/2000/svg"
                          viewBox="0 0 24 24"
                          fill="none"
                          stroke="currentColor"
                          strokeWidth="3"
                          strokeLinecap="round"
                          strokeLinejoin="round"
                        >
                          <path d="M5 12l5 5L20 7" />
                        </svg>
                      ) : (
                        <span>{index + 1}</span>
                      )}
                    </div>
                    <span className="status-step-label">{STATUS_LABELS[step]}</span>
                  </div>
                  {index < STATUS_STEPS.length - 1 && (
                    <div className={`status-step-connector ${isComplete ? 'complete' : ''}`} />
                  )}
                </div>
              );
            })}
          </div>

          <div className="current-status-display">
            <span className="current-status-label">Current Status:</span>
            <span className="current-status-value" data-testid="current-status">
              {STATUS_LABELS[currentStatus] || currentStatus}
            </span>
          </div>
        </div>

        {error && (
          <div className="order-error-banner" role="alert">
            <span className="error-icon" aria-hidden="true">⚠</span>
            <span className="error-message">{error}</span>
          </div>
        )}

        <div className="order-items-summary">
          <h2 className="order-items-title">Order Summary</h2>
          <ul className="order-items-list" role="list">
            {orderItems.map((item) => (
              <li key={item.menuItemId} className="order-item-row">
                <span className="order-item-name">{item.menuItemName}</span>
                <span className="order-item-quantity">×{item.quantity}</span>
                <span className="order-item-price">
                  ${(item.unitPrice * item.quantity).toFixed(2)}
                </span>
              </li>
            ))}
          </ul>
          <div className="order-total-row">
            <span className="order-total-label">Total</span>
            <span className="order-total-value">${totalAmount.toFixed(2)}</span>
          </div>
        </div>

        {statusHistory.length > 0 && (
          <div className="order-status-history">
            <h3 className="status-history-title">Status History</h3>
            <ul className="status-history-list" role="list">
              {statusHistory.map((entry, index) => (
                <li key={index} className="status-history-item">
                  <span className="status-history-status">{STATUS_LABELS[entry.status]}</span>
                  <span className="status-history-time">{formatTime(entry.updatedAt)}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        <div className="order-confirmation-actions">
          <button
            className="order-return-button"
            onClick={handleReturnToMenu}
            type="button"
          >
            Back to Menu
          </button>
        </div>
      </div>

      <style>{`
        .order-confirmation-page {
          display: flex;
          justify-content: center;
          align-items: flex-start;
          min-height: 100vh;
          padding: 2rem 1rem;
          background-color: var(--bg-primary, #f5f5f5);
        }

        .order-confirmation-card {
          background-color: var(--bg-card, #ffffff);
          border-radius: var(--radius-lg, 12px);
          box-shadow: var(--shadow-md, 0 4px 6px rgba(0, 0, 0, 0.1));
          padding: 2rem;
          max-width: 560px;
          width: 100%;
        }

        .order-confirmation-header {
          text-align: center;
          margin-bottom: 1.5rem;
        }

        .order-success-icon {
          width: 64px;
          height: 64px;
          margin: 0 auto 1rem;
          background-color: var(--color-success-bg, #e8f5e9);
          border-radius: 50%;
          display: flex;
          align-items: center;
          justify-content: center;
          color: var(--color-success, #4caf50);
        }

        .order-success-icon svg {
          width: 32px;
          height: 32px;
        }

        .order-confirmation-title {
          font-size: var(--font-size-xl, 1.5rem);
          font-weight: var(--font-weight-bold, 700);
          color: var(--text-primary, #1a1a1a);
          margin: 0 0 0.5rem;
        }

        .order-confirmation-subtitle {
          font-size: var(--font-size-base, 1rem);
          color: var(--text-secondary, #666666);
          margin: 0;
        }

        .order-number-section {
          background-color: var(--bg-secondary, #f9f9f9);
          border-radius: var(--radius-md, 8px);
          padding: 1rem;
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 1.5rem;
        }

        .order-number-label {
          font-size: var(--font-size-sm, 0.875rem);
          color: var(--text-secondary, #666666);
          font-weight: var(--font-weight-medium, 500);
        }

        .order-number-value {
          font-size: var(--font-size-lg, 1.125rem);
          font-weight: var(--font-weight-bold, 700);
          color: var(--text-primary, #1a1a1a);
          font-family: var(--font-mono, monospace);
        }

        .order-status-tracker {
          margin-bottom: 1.5rem;
        }

        .status-connection-indicator {
          display: flex;
          align-items: center;
          gap: 0.5rem;
          margin-bottom: 1rem;
          font-size: var(--font-size-xs, 0.75rem);
        }

        .connection-dot {
          width: 8px;
          height: 8px;
          border-radius: 50%;
          display: inline-block;
        }

        .connection-dot.connected {
          background-color: var(--color-success, #4caf50);
          animation: pulse 2s infinite;
        }

        .connection-dot.disconnected {
          background-color: var(--color-warning, #ff9800);
        }

        .connection-text {
          color: var(--text-secondary, #666666);
        }

        .status-steps {
          display: flex;
          align-items: flex-start;
          justify-content: space-between;
          margin-bottom: 1rem;
          position: relative;
        }

        .status-step-wrapper {
          display: flex;
          align-items: center;
          flex: 1;
        }

        .status-step-wrapper:last-child {
          flex: 0;
        }

        .status-step {
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 0.5rem;
          flex: 1;
        }

        .status-step-circle {
          width: 36px;
          height: 36px;
          border-radius: 50%;
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: var(--font-size-sm, 0.875rem);
          font-weight: var(--font-weight-bold, 700);
          background-color: var(--bg-tertiary, #e0e0e0);
          color: var(--text-secondary, #666666);
          transition: all 0.3s ease;
        }

        .status-step.complete .status-step-circle {
          background-color: var(--color-success, #4caf50);
          color: var(--text-on-primary, #ffffff);
        }

        .status-step.active .status-step-circle {
          background-color: var(--color-primary, #1976d2);
          color: var(--text-on-primary, #ffffff);
          box-shadow: 0 0 0 4px var(--color-primary-light, rgba(25, 118, 210, 0.2));
        }

        .status-step-circle svg {
          width: 18px;
          height: 18px;
        }

        .status-step-label {
          font-size: var(--font-size-xs, 0.75rem);
          color: var(--text-secondary, #666666);
          text-align: center;
          font-weight: var(--font-weight-medium, 500);
        }

        .status-step.complete .status-step-label,
        .status-step.active .status-step-label {
          color: var(--text-primary, #1a1a1a);
        }

        .status-step-connector {
          flex: 1;
          height: 2px;
          background-color: var(--bg-tertiary, #e0e0e0);
          margin: 0 0.25rem;
          align-self: center;
          margin-bottom: 1.5rem;
        }

        .status-step-connector.complete {
          background-color: var(--color-success, #4caf50);
        }

        .current-status-display {
          text-align: center;
          padding: 0.75rem;
          background-color: var(--bg-secondary, #f9f9f9);
          border-radius: var(--radius-md, 8px);
        }

        .current-status-label {
          font-size: var(--font-size-sm, 0.875rem);
          color: var(--text-secondary, #666666);
          margin-right: 0.5rem;
        }

        .current-status-value {
          font-size: var(--font-size-base, 1rem);
          font-weight: var(--font-weight-bold, 700);
          color: var(--color-primary, #1976d2);
        }

        .order-error-banner {
          display: flex;
          align-items: center;
          gap: 0.5rem;
          padding: 0.75rem 1rem;
          background-color: var(--color-error-bg, #ffebee);
          border-radius: var(--radius-md, 8px);
          margin-bottom: 1.5rem;
          font-size: var(--font-size-sm, 0.875rem);
          color: var(--color-error, #d32f2f);
        }

        .error-icon {
          font-size: var(--font-size-lg, 1.125rem);
        }

        .order-items-summary {
          border-top: 1px solid var(--border-color, #e0e0e0);
          padding-top: 1.5rem;
          margin-bottom: 1.5rem;
        }

        .order-items-title {
          font-size: var(--font-size-base, 1rem);
          font-weight: var(--font-weight-semibold, 600);
          color: var(--text-primary, #1a1a1a);
          margin: 0 0 1rem;
        }

        .order-items-list {
          list-style: none;
          padding: 0;
          margin: 0 0 1rem;
        }

        .order-item-row {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 0.5rem 0;
          border-bottom: 1px solid var(--border-light, #f0f0f0);
        }

        .order-item-name {
          font-size: var(--font-size-sm, 0.875rem);
          color: var(--text-primary, #1a1a1a);
          flex: 1;
        }

        .order-item-quantity {
          font-size: var(--font-size-sm, 0.875rem);
          color: var(--text-secondary, #666666);
          margin: 0 1rem;
        }

        .order-item-price {
          font-size: var(--font-size-sm, 0.875rem);
          font-weight: var(--font-weight-medium, 500);
          color: var(--text-primary, #1a1a1a);
        }

        .order-total-row {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding-top: 0.75rem;
          border-top: 2px solid var(--border-color, #e0e0e0);
        }

        .order-total-label {
          font-size: var(--font-size-base, 1rem);
          font-weight: var(--font-weight-semibold, 600);
          color: var(--text-primary, #1a1a1a);
        }

        .order-total-value {
          font-size: var(--font-size-lg, 1.125rem);
          font-weight: var(--font-weight-bold, 700);
          color: var(--text-primary, #1a1a1a);
        }

        .order-status-history {
          border-top: 1px solid var(--border-color, #e0e0e0);
          padding-top: 1.5rem;
          margin-bottom: 1.5rem;
        }

        .status-history-title {
          font-size: var(--font-size-base, 1rem);
          font-weight: var(--font-weight-semibold, 600);
          color: var(--text-primary, #1a1a1a);
          margin: 0 0 1rem;
        }

        .status-history-list {
          list-style: none;
          padding: 0;
          margin: 0;
        }

        .status-history-item {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 0.5rem 0;
          font-size: var(--font-size-sm, 0.875rem);
        }

        .status-history-status {
          color: var(--text-primary, #1a1a1a);
          font-weight: var(--font-weight-medium, 500);
        }

        .status-history-time {
          color: var(--text-secondary, #666666);
        }

        .order-confirmation-actions {
          text-align: center;
        }

        .order-return-button {
          background-color: var(--color-primary, #1976d2);
          color: var(--text-on-primary, #ffffff);
          border: none;
          border-radius: var(--radius-md, 8px);
          padding: 0.75rem 2rem;
          font-size: var(--font-size-base, 1rem);
          font-weight: var(--font-weight-medium, 500);
          cursor: pointer;
          transition: background-color 0.2s ease;
        }

        .order-return-button:hover {
          background-color: var(--color-primary-dark, #1565c0);
        }

        .order-return-button:focus {
          outline: 2px solid var(--color-primary, #1976d2);
          outline-offset: 2px;
        }

        @keyframes pulse {
          0%, 100% {
            opacity: 1;
          }
          50% {
            opacity: 0.5;
          }
        }
      `}</style>
    </div>
  );
};

export default OrderConfirmation;
