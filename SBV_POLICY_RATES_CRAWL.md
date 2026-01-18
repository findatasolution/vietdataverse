# SBV Policy Rates Crawl Implementation

## Overview
Thêm chức năng crawl 2 lãi suất chính sách của Ngân hàng Nhà nước (SBV):
- **Lãi suất tái chiết khấu** (Rediscount Rate)
- **Lãi suất tái cấp vốn** (Refinancing Rate)

## Source
**URL**: https://sbv.gov.vn/en/lãi-suất1

## Database Schema
**Table**: `vn_bank_termdepo`

**New Columns** (already created by user):
- `rediscount_rate` FLOAT - Lãi suất tái chiết khấu
- `refinancing_rate` FLOAT - Lãi suất tái cấp vốn

## Implementation

### Location
**File**: `crawl_tools/crawl_bot.py`
**Lines**: 315-390

### Logic Flow

```
1. Fetch https://sbv.gov.vn/en/lãi-suất1
   ↓
2. Parse HTML tables to find rates
   - Search for "tái chiết khấu" or "rediscount"
   - Search for "tái cấp vốn" or "refinancing"
   ↓
3. Extract numeric values (e.g., "3.000%" → 3.0)
   ↓
4. Update ALL bank records for today with these policy rates
   - Get distinct bank_code from vn_bank_termdepo WHERE date = today
   - UPDATE each bank record with the policy rates
   ↓
5. Log success/failure
```

### Key Features

✅ **Bilingual Search**: Searches for both Vietnamese and English terms
- Vietnamese: "tái chiết khấu", "tái cấp vốn"
- English: "rediscount", "refinancing"

✅ **Robust Parsing**:
- Handles percentage signs
- Converts commas to decimal points
- Strips whitespace

✅ **Applies to All Banks**:
- Policy rates từ SBV apply uniformly to all banks
- Updates all bank records for current date

✅ **Error Handling**:
- Traceback on errors for debugging
- Continues execution if rates not found

## Code Snippet

```python
# Extract rate from table cell
rate_value = float(rate_value_text.replace('%', '').replace(',', '.').strip())

# Check for rate types
if 'tái chiết khấu' in rate_type.lower() or 'rediscount' in rate_type.lower():
    rediscount_rate = rate_value

if 'tái cấp vốn' in rate_type.lower() or 'refinancing' in rate_type.lower():
    refinancing_rate = rate_value

# Update all banks for today
UPDATE vn_bank_termdepo
SET rediscount_rate = :rediscount_rate,
    refinancing_rate = :refinancing_rate
WHERE date = :date AND bank_code = :bank_code
```

## Expected Output

### Success
```
Found Rediscount Rate: 3.0%
Found Refinancing Rate: 4.5%
✅ Updated SBV policy rates for 5 banks on 2026-01-18
```

### No Bank Records
```
Found Rediscount Rate: 3.0%
Found Refinancing Rate: 4.5%
⚠️  No bank records found for 2026-01-18, cannot update SBV policy rates
```

### Rates Not Found
```
❌ Could not find rediscount or refinancing rates on SBV page
```

### Error
```
❌ Error crawling SBV policy rates: [error message]
[full traceback]
```

## Data Flow

```
Daily Crawl (crawl_bot.py)
    │
    ├─ Crawl ACB/VCB/etc. → vn_bank_termdepo (term_1m, term_3m, ...)
    │
    └─ Crawl SBV Policy Rates → UPDATE vn_bank_termdepo (rediscount_rate, refinancing_rate)
```

**Timing**: SBV policy rates section runs AFTER bank term deposit rates are crawled

## Database Example

After crawling ACB + SBV policy rates:

| date       | bank_code | term_1m | term_3m | ... | rediscount_rate | refinancing_rate | crawl_time          |
|------------|-----------|---------|---------|-----|-----------------|------------------|---------------------|
| 2026-01-18 | ACB       | 3.5     | 4.2     | ... | 3.0             | 4.5              | 2026-01-18 08:30:15 |
| 2026-01-18 | VCB       | 3.3     | 4.0     | ... | 3.0             | 4.5              | 2026-01-18 08:30:20 |

**Note**:
- `rediscount_rate` và `refinancing_rate` are same across all banks (policy rates)
- `term_1m`, `term_3m`, etc. vary by bank (deposit rates)

## Testing

### Manual Test
```bash
cd crawl_tools
python crawl_bot.py
```

**Check output for:**
```
Found Rediscount Rate: X.X%
Found Refinancing Rate: Y.Y%
✅ Updated SBV policy rates for N banks on YYYY-MM-DD
```

### Database Verification
```sql
-- Check if rates were updated
SELECT bank_code, rediscount_rate, refinancing_rate
FROM vn_bank_termdepo
WHERE date = '2026-01-18';

-- Expected: All banks have same rediscount_rate and refinancing_rate values
```

## Edge Cases Handled

1. **No bank records for today**
   - Output: Warning message
   - Action: Skip update (nothing to update)

2. **Only one rate found**
   - Updates the found rate, leaves other as NULL
   - Continues execution

3. **Parsing errors**
   - Catches ValueError, AttributeError
   - Continues searching other rows

4. **Network errors**
   - Catches exception
   - Prints error with traceback
   - Continues with rest of crawl

## Current Rates (as of crawl)

From https://sbv.gov.vn/en/lãi-suất1 (last checked):
- **Rediscount Rate**: 3.000%
- **Refinancing Rate**: 4.500%
- **Effective Date**: 19/06/2023 (Decision 1123/QĐ-NHNN)

## Future Enhancements

### Optional: Track Rate Changes
Could add a separate table to track historical policy rate changes:

```sql
CREATE TABLE sbv_policy_rates_history (
    effective_date DATE PRIMARY KEY,
    rediscount_rate FLOAT,
    refinancing_rate FLOAT,
    decision_number VARCHAR(50),
    crawl_time TIMESTAMP
);
```

### Optional: Parse Decision Number
Extract decision number and effective date from the SBV page for audit trail.

### Optional: Alert on Rate Changes
Send notification if policy rates change from previous crawl.

## Dependencies

- `requests` - HTTP requests
- `beautifulsoup4` - HTML parsing
- `sqlalchemy` - Database operations

No additional dependencies needed (already in requirements.txt).

## Integration with Existing Workflow

**GitHub Actions** (`.github/workflows/daily-crawl.yml`):
```yaml
- name: Run crawl bot
  run: |
    cd crawl_tools
    python crawl_bot.py
```

Runs daily at 8:30 AM VN time (1:30 AM UTC).

SBV policy rates will be updated automatically as part of daily crawl.

## Notes

- SBV policy rates change infrequently (quarterly or less)
- Page structure may change, requiring code updates
- Bilingual search makes it more robust to Vietnamese/English toggles on SBV website
- Policy rates apply nationwide, so updating all banks makes sense

## Rollback

If issues occur, can temporarily disable by commenting out lines 315-390 in `crawl_bot.py`.

Data remains in database (won't be overwritten).
