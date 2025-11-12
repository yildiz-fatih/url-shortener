# URL Shortener


## How to Run


## System Design

### Making Redirects as Fast as Possible 

The `GET /{short_code}` endpoint must respond quickly as possible. The naive solution would be to query the database for every single request, but this becomes an I/O bottleneck and doesn't scale well.

#### Solution: Database Indexing:

By indexing the `short_code` column, the database can find the corresponding long URL in **O(log N)** time instead of performing a full table scan (**O(N)**).  
This provides an improvement but still depends on disk I/O.

#### Solution: Caching with an In-Memory Key–Value Store (Redis)

Disk reads are inherently slower than memory access. To minimize latency, the service uses Redis as an in-memory cache.

**Cache-Aside Pattern**
- On a redirect request, the service first checks Redis for the short code.
- If found, the long URL is returned directly from cache.
- If not found, the service queries the database, retrieves the long URL, stores it in Redis for future requests, and then redirects the user.

---

### Cache-Database Inconsistencies

If Redis is down during a `DELETE` operation, the database successfully removes the entry, but the cache invalidation fails. When Redis recovers, it may still have the deleted short code.
This leads to a **cache–database inconsistency**, where users continue to receive a deleted URL.

#### Solution: Best Effort Invalidation with TTL Fallback**

Every cached entry is set with a Time to Live (TTL) of 5 minutes. This ensures that even if cache invalidation fails, stale entries automatically expire after their TTL.

This design allows the system to maintain *high availability* while providing *eventual consistency* between the cache and the database.

---
