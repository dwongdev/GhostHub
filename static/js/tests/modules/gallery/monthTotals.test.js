/**
 * @vitest-environment jsdom
 */

import { afterEach, beforeEach, describe, expect, it } from 'vitest';

describe('gallery month totals', () => {
  let clearAllMedia;
  let setAllYearsData;
  let setDateTotals;
  let getMonthTotal;

  beforeEach(async () => {
    ({
      clearAllMedia,
      setAllYearsData,
      setDateTotals,
      getMonthTotal
    } = await import('../../../modules/layouts/gallery/state.js'));

    clearAllMedia();
  });

  afterEach(() => {
    clearAllMedia();
    setAllYearsData([]);
    setDateTotals({});
  });

  it('prefers canonical month totals from allYearsData over loaded date slices', () => {
    setAllYearsData([
      {
        year: 2024,
        months: [
          { month: 9, dateKey: '2024-09-11', media_count: 23 }
        ]
      }
    ]);
    setDateTotals({
      '2024-09-11': 5,
      '2024-09-08': 18
    });

    expect(getMonthTotal('2024-09-11')).toBe(23);
    expect(getMonthTotal('2024-09-08')).toBe(23);
  });

  it('falls back to summing loaded date totals when month metadata is unavailable', () => {
    setAllYearsData([]);
    setDateTotals({
      '2024-09-11': 5,
      '2024-09-08': 18
    });

    expect(getMonthTotal('2024-09-11')).toBe(23);
  });
});
