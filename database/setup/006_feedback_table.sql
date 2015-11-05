CREATE TABLE feedback(
    id          SERIAL PRIMARY KEY,
    feedback    VARCHAR NOT NULL UNIQUE,
    time        TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);
