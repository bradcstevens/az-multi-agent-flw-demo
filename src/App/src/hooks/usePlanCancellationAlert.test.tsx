import { describe, expect, it, vi } from 'vitest';
import { renderHook } from '@testing-library/react';
import { PlanStatus } from '../models';
import { usePlanCancellationAlert } from './usePlanCancellationAlert';

describe('the Plan record cancellation predicate', () => {
    it('requires confirmation for an approved Deliberate request', () => {
        const { result } = renderHook(() =>
            usePlanCancellationAlert({
                planData: {
                    plan: {
                        lane: 'deliberate',
                        overall_status: PlanStatus.APPROVED,
                    },
                },
                planApprovalRequest: undefined,
                onNavigate: vi.fn(),
            }),
        );

        expect(result.current.requiresCancellationConfirmation()).toBe(true);
    });
});
