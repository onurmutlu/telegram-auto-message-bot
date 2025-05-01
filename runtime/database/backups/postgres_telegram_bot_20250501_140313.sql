--
-- PostgreSQL database dump
--

-- Dumped from database version 14.17 (Homebrew)
-- Dumped by pg_dump version 14.17 (Homebrew)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: category_groups; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.category_groups (
    id integer NOT NULL,
    group_id bigint,
    category text NOT NULL,
    source text,
    confidence integer DEFAULT 1,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.category_groups OWNER TO postgres;

--
-- Name: category_groups_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.category_groups_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.category_groups_id_seq OWNER TO postgres;

--
-- Name: category_groups_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.category_groups_id_seq OWNED BY public.category_groups.id;


--
-- Name: config; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.config (
    key text NOT NULL,
    value text
);


ALTER TABLE public.config OWNER TO postgres;

--
-- Name: data_mining; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.data_mining (
    mining_id integer NOT NULL,
    user_id bigint,
    telegram_id bigint,
    type character varying(50),
    source character varying(100),
    data jsonb,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.data_mining OWNER TO postgres;

--
-- Name: data_mining_mining_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.data_mining_mining_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.data_mining_mining_id_seq OWNER TO postgres;

--
-- Name: data_mining_mining_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.data_mining_mining_id_seq OWNED BY public.data_mining.mining_id;


--
-- Name: debug_bot_users; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.debug_bot_users (
    id integer NOT NULL,
    user_id integer,
    username character varying,
    first_name character varying,
    last_name character varying,
    access_level character varying,
    first_seen timestamp without time zone,
    last_seen timestamp without time zone,
    is_developer boolean DEFAULT false,
    is_superuser boolean DEFAULT false,
    is_active boolean DEFAULT true,
    created_at timestamp without time zone,
    updated_at timestamp without time zone
);


ALTER TABLE public.debug_bot_users OWNER TO postgres;

--
-- Name: debug_bot_users_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.debug_bot_users_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.debug_bot_users_id_seq OWNER TO postgres;

--
-- Name: debug_bot_users_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.debug_bot_users_id_seq OWNED BY public.debug_bot_users.id;


--
-- Name: group_analytics; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.group_analytics (
    id integer NOT NULL,
    group_id bigint,
    analysis_data jsonb,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.group_analytics OWNER TO postgres;

--
-- Name: group_analytics_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.group_analytics_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.group_analytics_id_seq OWNER TO postgres;

--
-- Name: group_analytics_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.group_analytics_id_seq OWNED BY public.group_analytics.id;


--
-- Name: groups; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.groups (
    id integer NOT NULL,
    group_id bigint NOT NULL,
    name text,
    join_date timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    last_message timestamp without time zone,
    message_count integer DEFAULT 0,
    member_count integer DEFAULT 0,
    error_count integer DEFAULT 0,
    last_error text,
    is_active boolean DEFAULT true,
    permanent_error boolean DEFAULT false,
    is_target boolean DEFAULT false,
    retry_after timestamp without time zone,
    is_admin boolean DEFAULT false,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.groups OWNER TO postgres;

--
-- Name: groups_backup; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.groups_backup (
    id integer,
    group_id bigint,
    name text,
    join_date timestamp without time zone,
    last_message timestamp without time zone,
    message_count integer,
    member_count integer,
    error_count integer,
    last_error text,
    is_active boolean,
    permanent_error boolean,
    is_target boolean,
    retry_after timestamp without time zone,
    is_admin boolean,
    created_at timestamp without time zone,
    updated_at timestamp without time zone
);


ALTER TABLE public.groups_backup OWNER TO postgres;

--
-- Name: groups_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.groups_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.groups_id_seq OWNER TO postgres;

--
-- Name: groups_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.groups_id_seq OWNED BY public.groups.id;


--
-- Name: message_templates; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.message_templates (
    id integer NOT NULL,
    content text NOT NULL,
    category text,
    language text DEFAULT 'tr'::text,
    type text DEFAULT 'general'::text,
    is_active boolean DEFAULT true,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.message_templates OWNER TO postgres;

--
-- Name: message_templates_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.message_templates_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.message_templates_id_seq OWNER TO postgres;

--
-- Name: message_templates_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.message_templates_id_seq OWNED BY public.message_templates.id;


--
-- Name: messages; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.messages (
    id integer NOT NULL,
    group_id bigint,
    content text,
    sent_at timestamp without time zone,
    status text,
    error text,
    is_active boolean DEFAULT true,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.messages OWNER TO postgres;

--
-- Name: messages_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.messages_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.messages_id_seq OWNER TO postgres;

--
-- Name: messages_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.messages_id_seq OWNED BY public.messages.id;


--
-- Name: migrations; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.migrations (
    id integer NOT NULL,
    version character varying(20),
    applied_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.migrations OWNER TO postgres;

--
-- Name: migrations_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.migrations_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.migrations_id_seq OWNER TO postgres;

--
-- Name: migrations_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.migrations_id_seq OWNED BY public.migrations.id;


--
-- Name: mining_data; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.mining_data (
    id integer NOT NULL,
    user_id bigint NOT NULL,
    username text,
    first_name text,
    last_name text,
    group_id bigint,
    group_name text,
    message_count integer DEFAULT 0,
    first_seen timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    last_seen timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    is_active boolean DEFAULT true,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.mining_data OWNER TO postgres;

--
-- Name: mining_data_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.mining_data_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.mining_data_id_seq OWNER TO postgres;

--
-- Name: mining_data_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.mining_data_id_seq OWNED BY public.mining_data.id;


--
-- Name: mining_logs; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.mining_logs (
    id integer NOT NULL,
    mining_id bigint,
    action_type text,
    details text,
    "timestamp" timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    success boolean,
    error text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    user_id bigint,
    telegram_id bigint
);


ALTER TABLE public.mining_logs OWNER TO postgres;

--
-- Name: mining_logs_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.mining_logs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.mining_logs_id_seq OWNER TO postgres;

--
-- Name: mining_logs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.mining_logs_id_seq OWNED BY public.mining_logs.id;


--
-- Name: settings; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.settings (
    id integer NOT NULL,
    key text NOT NULL,
    value text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.settings OWNER TO postgres;

--
-- Name: settings_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.settings_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.settings_id_seq OWNER TO postgres;

--
-- Name: settings_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.settings_id_seq OWNED BY public.settings.id;


--
-- Name: spam_messages; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.spam_messages (
    id integer NOT NULL,
    content text,
    category text,
    is_active boolean DEFAULT true,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    created_by text,
    language text DEFAULT 'tr'::text
);


ALTER TABLE public.spam_messages OWNER TO postgres;

--
-- Name: spam_messages_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.spam_messages_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.spam_messages_id_seq OWNER TO postgres;

--
-- Name: spam_messages_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.spam_messages_id_seq OWNED BY public.spam_messages.id;


--
-- Name: user_activity; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.user_activity (
    id integer NOT NULL,
    user_id bigint,
    action text NOT NULL,
    details jsonb,
    ip_address text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    session_id text
);


ALTER TABLE public.user_activity OWNER TO postgres;

--
-- Name: user_activity_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.user_activity_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.user_activity_id_seq OWNER TO postgres;

--
-- Name: user_activity_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.user_activity_id_seq OWNED BY public.user_activity.id;


--
-- Name: user_bio_links; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.user_bio_links (
    id integer NOT NULL,
    user_id bigint,
    link_type text,
    link_url text NOT NULL,
    is_verified boolean DEFAULT false,
    group_id bigint,
    discovered_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    last_checked timestamp without time zone,
    is_active boolean DEFAULT true
);


ALTER TABLE public.user_bio_links OWNER TO postgres;

--
-- Name: user_bio_links_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.user_bio_links_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.user_bio_links_id_seq OWNER TO postgres;

--
-- Name: user_bio_links_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.user_bio_links_id_seq OWNED BY public.user_bio_links.id;


--
-- Name: user_bio_scan_logs; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.user_bio_scan_logs (
    id integer NOT NULL,
    user_id bigint,
    scan_results jsonb,
    scanned_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.user_bio_scan_logs OWNER TO postgres;

--
-- Name: user_bio_scan_logs_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.user_bio_scan_logs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.user_bio_scan_logs_id_seq OWNER TO postgres;

--
-- Name: user_bio_scan_logs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.user_bio_scan_logs_id_seq OWNED BY public.user_bio_scan_logs.id;


--
-- Name: user_demographics; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.user_demographics (
    id integer NOT NULL,
    user_id bigint,
    language text,
    bio_keywords text,
    country text,
    interests text[],
    profile_picture_url text,
    last_updated timestamp without time zone,
    verified boolean DEFAULT false,
    premium boolean DEFAULT false,
    mutual_contact boolean DEFAULT false,
    common_chats_count integer DEFAULT 0,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    sentiments jsonb
);


ALTER TABLE public.user_demographics OWNER TO postgres;

--
-- Name: user_demographics_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.user_demographics_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.user_demographics_id_seq OWNER TO postgres;

--
-- Name: user_demographics_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.user_demographics_id_seq OWNED BY public.user_demographics.id;


--
-- Name: user_group_activity; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.user_group_activity (
    id integer NOT NULL,
    user_id bigint,
    group_id bigint,
    last_seen timestamp without time zone,
    is_active boolean DEFAULT true,
    is_admin boolean DEFAULT false,
    message_count integer DEFAULT 0,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.user_group_activity OWNER TO postgres;

--
-- Name: user_group_activity_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.user_group_activity_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.user_group_activity_id_seq OWNER TO postgres;

--
-- Name: user_group_activity_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.user_group_activity_id_seq OWNED BY public.user_group_activity.id;


--
-- Name: user_group_relation; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.user_group_relation (
    id integer NOT NULL,
    user_id bigint,
    group_id bigint,
    is_admin boolean DEFAULT false,
    join_date timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    message_count integer DEFAULT 0,
    last_activity timestamp without time zone,
    is_active boolean DEFAULT true,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.user_group_relation OWNER TO postgres;

--
-- Name: user_group_relation_backup; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.user_group_relation_backup (
    id integer,
    user_id bigint,
    group_id bigint,
    is_admin boolean,
    join_date timestamp without time zone,
    message_count integer,
    last_activity timestamp without time zone,
    is_active boolean,
    created_at timestamp without time zone,
    updated_at timestamp without time zone
);


ALTER TABLE public.user_group_relation_backup OWNER TO postgres;

--
-- Name: user_group_relation_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.user_group_relation_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.user_group_relation_id_seq OWNER TO postgres;

--
-- Name: user_group_relation_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.user_group_relation_id_seq OWNED BY public.user_group_relation.id;


--
-- Name: user_groups; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.user_groups (
    id integer NOT NULL,
    user_id bigint,
    group_id bigint,
    join_date timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    is_admin boolean DEFAULT false,
    rank integer DEFAULT 0,
    message_count integer DEFAULT 0,
    last_message timestamp without time zone,
    is_active boolean DEFAULT true,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.user_groups OWNER TO postgres;

--
-- Name: user_groups_backup; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.user_groups_backup (
    id integer,
    user_id bigint,
    group_id bigint,
    join_date timestamp without time zone,
    is_admin boolean,
    rank integer,
    message_count integer,
    last_message timestamp without time zone,
    is_active boolean,
    created_at timestamp without time zone,
    updated_at timestamp without time zone
);


ALTER TABLE public.user_groups_backup OWNER TO postgres;

--
-- Name: user_groups_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.user_groups_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.user_groups_id_seq OWNER TO postgres;

--
-- Name: user_groups_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.user_groups_id_seq OWNED BY public.user_groups.id;


--
-- Name: user_invites; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.user_invites (
    id integer NOT NULL,
    user_id bigint,
    username text,
    invite_link text NOT NULL,
    group_id bigint,
    status text DEFAULT 'pending'::text,
    invited_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    joined_at timestamp without time zone,
    last_invite_date timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    is_active boolean DEFAULT true,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.user_invites OWNER TO postgres;

--
-- Name: user_invites_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.user_invites_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.user_invites_id_seq OWNER TO postgres;

--
-- Name: user_invites_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.user_invites_id_seq OWNED BY public.user_invites.id;


--
-- Name: users; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.users (
    id integer NOT NULL,
    user_id bigint NOT NULL,
    username text,
    first_name text,
    last_name text,
    is_active boolean DEFAULT true,
    join_date timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    last_seen timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.users OWNER TO postgres;

--
-- Name: users_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.users_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.users_id_seq OWNER TO postgres;

--
-- Name: users_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.users_id_seq OWNED BY public.users.id;


--
-- Name: category_groups id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.category_groups ALTER COLUMN id SET DEFAULT nextval('public.category_groups_id_seq'::regclass);


--
-- Name: data_mining mining_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.data_mining ALTER COLUMN mining_id SET DEFAULT nextval('public.data_mining_mining_id_seq'::regclass);


--
-- Name: debug_bot_users id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.debug_bot_users ALTER COLUMN id SET DEFAULT nextval('public.debug_bot_users_id_seq'::regclass);


--
-- Name: group_analytics id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.group_analytics ALTER COLUMN id SET DEFAULT nextval('public.group_analytics_id_seq'::regclass);


--
-- Name: groups id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.groups ALTER COLUMN id SET DEFAULT nextval('public.groups_id_seq'::regclass);


--
-- Name: message_templates id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.message_templates ALTER COLUMN id SET DEFAULT nextval('public.message_templates_id_seq'::regclass);


--
-- Name: messages id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.messages ALTER COLUMN id SET DEFAULT nextval('public.messages_id_seq'::regclass);


--
-- Name: migrations id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.migrations ALTER COLUMN id SET DEFAULT nextval('public.migrations_id_seq'::regclass);


--
-- Name: mining_data id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.mining_data ALTER COLUMN id SET DEFAULT nextval('public.mining_data_id_seq'::regclass);


--
-- Name: mining_logs id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.mining_logs ALTER COLUMN id SET DEFAULT nextval('public.mining_logs_id_seq'::regclass);


--
-- Name: settings id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.settings ALTER COLUMN id SET DEFAULT nextval('public.settings_id_seq'::regclass);


--
-- Name: spam_messages id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.spam_messages ALTER COLUMN id SET DEFAULT nextval('public.spam_messages_id_seq'::regclass);


--
-- Name: user_activity id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.user_activity ALTER COLUMN id SET DEFAULT nextval('public.user_activity_id_seq'::regclass);


--
-- Name: user_bio_links id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.user_bio_links ALTER COLUMN id SET DEFAULT nextval('public.user_bio_links_id_seq'::regclass);


--
-- Name: user_bio_scan_logs id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.user_bio_scan_logs ALTER COLUMN id SET DEFAULT nextval('public.user_bio_scan_logs_id_seq'::regclass);


--
-- Name: user_demographics id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.user_demographics ALTER COLUMN id SET DEFAULT nextval('public.user_demographics_id_seq'::regclass);


--
-- Name: user_group_activity id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.user_group_activity ALTER COLUMN id SET DEFAULT nextval('public.user_group_activity_id_seq'::regclass);


--
-- Name: user_group_relation id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.user_group_relation ALTER COLUMN id SET DEFAULT nextval('public.user_group_relation_id_seq'::regclass);


--
-- Name: user_groups id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.user_groups ALTER COLUMN id SET DEFAULT nextval('public.user_groups_id_seq'::regclass);


--
-- Name: user_invites id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.user_invites ALTER COLUMN id SET DEFAULT nextval('public.user_invites_id_seq'::regclass);


--
-- Name: users id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.users ALTER COLUMN id SET DEFAULT nextval('public.users_id_seq'::regclass);


--
-- Data for Name: category_groups; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.category_groups (id, group_id, category, source, confidence, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: config; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.config (key, value) FROM stdin;
telethon_session	1BJWap1sBuwFmA5dTt53Vzs21Cz497ByjJXKzFmc-0Ut54tOZ_lMXYATC2Boc30T479BzZNHVL7aJW0a9BSfrR544agMV5nd464gpC1Hk-O7y8_gobCGYL5WEJeC9cCvHxYDbXl1iOFQR1XVNM2I08kFoK-U4DOB9IzSMUvyK7ccKtRJY559eMGtmCQtXff7uv_OsvpKUE4fjy8fKCYaryOujM65bOp-zM9fpla7qoyp9l-opIuJmpa_J7P1iCG0UPiq3Kxw31fYdA8-Fm2lnSgLfmXrlf9AKmVW9g3udT_UdCQWyqcg0JkhoANft6jVi20qSMxWcSK8OCO0dNMv1AVe0v6e2yu0=
\.


--
-- Data for Name: data_mining; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.data_mining (mining_id, user_id, telegram_id, type, source, data, created_at) FROM stdin;
\.


--
-- Data for Name: debug_bot_users; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.debug_bot_users (id, user_id, username, first_name, last_name, access_level, first_seen, last_seen, is_developer, is_superuser, is_active, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: group_analytics; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.group_analytics (id, group_id, analysis_data, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: groups; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.groups (id, group_id, name, join_date, last_message, message_count, member_count, error_count, last_error, is_active, permanent_error, is_target, retry_after, is_admin, created_at, updated_at) FROM stdin;
1	-1	Örnek Grup	2025-05-01 13:56:39.334849	\N	0	0	0	\N	t	f	f	\N	t	2025-05-01 13:56:39.967077	2025-05-01 13:56:39.967077
2	-2	Test Grubu	2025-05-01 13:56:39.334849	\N	0	0	0	\N	t	f	f	\N	f	2025-05-01 13:56:39.967077	2025-05-01 13:56:39.967077
3	-3	Duyuru Grubu	2025-05-01 13:56:39.334849	\N	0	0	0	\N	t	f	f	\N	t	2025-05-01 13:56:39.967077	2025-05-01 13:56:39.967077
4	-2483982810	𝐀𝐑𝐀𝐘𝐈𝐒̧ 𝐒𝐎𝐇𝐁𝐄𝐓 PREMIUM	2025-05-01 14:03:06.819917	\N	0	0	0	\N	t	f	f	\N	f	2025-05-01 14:03:06.820015	2025-05-01 14:03:06.820015
5	-2287527154	𝐀𝐑𝐀𝐘𝐈𝐒̧ Premium	2025-05-01 14:03:06.822941	\N	0	0	0	\N	t	f	f	\N	f	2025-05-01 14:03:06.823045	2025-05-01 14:03:06.823045
6	-2371773638	Arayış #Taciz Sohbet 💓	2025-05-01 14:03:06.826045	\N	0	0	0	\N	t	f	f	\N	f	2025-05-01 14:03:06.826236	2025-05-01 14:03:06.826236
7	-2472982388	Arayış Grubu TOPLANIYORUZ	2025-05-01 14:03:06.829177	\N	0	0	0	\N	t	f	f	\N	f	2025-05-01 14:03:06.82928	2025-05-01 14:03:06.82928
8	-2269922362	Türkiye Arayış Sohbet +18	2025-05-01 14:03:06.833047	\N	0	0	0	\N	t	f	f	\N	f	2025-05-01 14:03:06.833168	2025-05-01 14:03:06.833168
9	-2233445352	𝐇𝐀𝐓𝐔𝐍 𝐀𝐑𝐀𝐘𝐈Ş𝐋𝐀𝐑	2025-05-01 14:03:06.836056	\N	0	0	0	\N	t	f	f	\N	f	2025-05-01 14:03:06.836459	2025-05-01 14:03:06.836459
10	-1686321334	ARAYIŞ BULMA TÜRKİYE 🇹🇷	2025-05-01 14:03:06.840395	\N	0	0	0	\N	t	f	f	\N	f	2025-05-01 14:03:06.840607	2025-05-01 14:03:06.840607
11	-2415733440	Aktif Arayışlar Vip 👅 katıl sohbet sex +18 kanal grup Ankara İstanbul İzmir	2025-05-01 14:03:06.843062	\N	0	0	0	\N	t	f	f	\N	f	2025-05-01 14:03:06.843233	2025-05-01 14:03:06.843233
12	-2638568724	🇹🇷 𝙏𝙐𝙍𝙆𝙄𝙔𝙀 𝘼𝙍𝘼𝙔𝙄𝙎 🇹🇷	2025-05-01 14:03:06.868123	\N	0	0	0	\N	t	f	f	\N	f	2025-05-01 14:03:06.868335	2025-05-01 14:03:06.868335
13	-2460599280	K I Z ＡＲＡＹＩＳ	2025-05-01 14:03:06.891082	\N	0	0	0	\N	t	f	f	\N	f	2025-05-01 14:03:06.891215	2025-05-01 14:03:06.891215
14	-1952919795	Arayış +18 #xHumster	2025-05-01 14:03:06.914336	\N	0	0	0	\N	t	f	f	\N	f	2025-05-01 14:03:06.915292	2025-05-01 14:03:06.915292
15	-2314168327	𝗧𝗨̈𝗥𝗞𝗜̇𝗬𝗘 𝗔𝗥𝗔𝗬𝗜𝗦̧ 𝗚𝗥𝗨𝗕𝗨 🇹🇷	2025-05-01 14:03:06.952075	\N	0	0	0	\N	t	f	f	\N	f	2025-05-01 14:03:06.952415	2025-05-01 14:03:06.952415
16	-2367554811	ONLY ARAYIŞ TR 🇹🇷	2025-05-01 14:03:06.956376	\N	0	0	0	\N	t	f	f	\N	f	2025-05-01 14:03:06.956491	2025-05-01 14:03:06.956491
17	-2158651056	Kız Bulma Arayış Grubu 💕	2025-05-01 14:03:06.959126	\N	0	0	0	\N	t	f	f	\N	f	2025-05-01 14:03:06.959232	2025-05-01 14:03:06.959232
18	-2607016335	ULTRA ARAYIŞ	2025-05-01 14:03:06.962899	\N	0	0	0	\N	t	f	f	\N	f	2025-05-01 14:03:06.965141	2025-05-01 14:03:06.965141
19	-2429543399	Jigolo Ajansı	2025-05-01 14:03:06.96782	\N	0	0	0	\N	t	f	f	\N	f	2025-05-01 14:03:06.967971	2025-05-01 14:03:06.967971
20	-2424753000	Adana Arayış Tanışma Sohbet Grubu	2025-05-01 14:03:06.970576	\N	0	0	0	\N	t	f	f	\N	f	2025-05-01 14:03:06.970685	2025-05-01 14:03:06.970685
21	-2222641573	Arayıs Sohbet	2025-05-01 14:03:06.973298	\N	0	0	0	\N	t	f	f	\N	f	2025-05-01 14:03:06.973406	2025-05-01 14:03:06.973406
22	-2316064460	+18 CHAT	2025-05-01 14:03:06.976965	\N	0	0	0	\N	t	f	f	\N	f	2025-05-01 14:03:06.977082	2025-05-01 14:03:06.977082
23	-2275752197	EVLİLİK_ARAYIS	2025-05-01 14:03:06.979736	\N	0	0	0	\N	t	f	f	\N	f	2025-05-01 14:03:06.979854	2025-05-01 14:03:06.979854
24	-2491181978	Jigolo - Escort - Gay Yönlendirme ve Arayış Grubu	2025-05-01 14:03:06.984811	\N	0	0	0	\N	t	f	f	\N	f	2025-05-01 14:03:06.984951	2025-05-01 14:03:06.984951
25	-2208688666	ARAYIŞLAR SOHBET GRUBU	2025-05-01 14:03:06.987529	\N	0	0	0	\N	t	f	f	\N	f	2025-05-01 14:03:06.9879	2025-05-01 14:03:06.9879
26	-2435996914	Arayış Sohbet Grubu 🇹🇷	2025-05-01 14:03:06.99241	\N	0	0	0	\N	t	f	f	\N	f	2025-05-01 14:03:06.992547	2025-05-01 14:03:06.992547
27	-2322844801	Arayış Tanışma Sohbet Grubu	2025-05-01 14:03:07.00241	\N	0	0	0	\N	t	f	f	\N	f	2025-05-01 14:03:07.004972	2025-05-01 14:03:07.004972
28	-2356840702	Türkiye Arayış Sohbet Grubu	2025-05-01 14:03:07.009075	\N	0	0	0	\N	t	f	f	\N	f	2025-05-01 14:03:07.009321	2025-05-01 14:03:07.009321
29	-2272765147	Escort Arayış Grubu	2025-05-01 14:03:07.014155	\N	0	0	0	\N	t	f	f	\N	f	2025-05-01 14:03:07.014927	2025-05-01 14:03:07.014927
30	-2450655557	ARAYIŞ MERKEZİ	2025-05-01 14:03:07.019189	\N	0	0	0	\N	t	f	f	\N	f	2025-05-01 14:03:07.019415	2025-05-01 14:03:07.019415
31	-2443554947	TR SOHBET ARAYIŞ +18 🇹🇷	2025-05-01 14:03:07.022536	\N	0	0	0	\N	t	f	f	\N	f	2025-05-01 14:03:07.022651	2025-05-01 14:03:07.022651
32	-2476886843	.	2025-05-01 14:03:07.025452	\N	0	0	0	\N	t	f	f	\N	f	2025-05-01 14:03:07.025553	2025-05-01 14:03:07.025553
33	-2267882898	BİHTER TENDU GÜNCEL	2025-05-01 14:03:07.029263	\N	0	0	0	\N	t	f	f	\N	f	2025-05-01 14:03:07.029416	2025-05-01 14:03:07.029416
34	-2393818027	Tango,stripchat, premium👙	2025-05-01 14:03:07.03408	\N	0	0	0	\N	t	f	f	\N	f	2025-05-01 14:03:07.034354	2025-05-01 14:03:07.034354
35	-4640967674	ARAYIŞ OnlyVips	2025-05-01 14:03:07.037282	\N	0	0	0	\N	t	f	f	\N	f	2025-05-01 14:03:07.037393	2025-05-01 14:03:07.037393
36	-2536585408	ARAYIŞ OnlyVips	2025-05-01 14:03:07.039907	\N	0	0	0	\N	t	f	f	\N	f	2025-05-01 14:03:07.040014	2025-05-01 14:03:07.040014
\.


--
-- Data for Name: groups_backup; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.groups_backup (id, group_id, name, join_date, last_message, message_count, member_count, error_count, last_error, is_active, permanent_error, is_target, retry_after, is_admin, created_at, updated_at) FROM stdin;
1	-1	Örnek Grup	2025-05-01 13:56:39.334849	\N	0	0	0	\N	t	f	f	\N	t	2025-05-01 13:56:39.334849	2025-05-01 13:56:39.334849
2	-2	Test Grubu	2025-05-01 13:56:39.334849	\N	0	0	0	\N	t	f	f	\N	f	2025-05-01 13:56:39.334849	2025-05-01 13:56:39.334849
3	-3	Duyuru Grubu	2025-05-01 13:56:39.334849	\N	0	0	0	\N	t	f	f	\N	t	2025-05-01 13:56:39.334849	2025-05-01 13:56:39.334849
\.


--
-- Data for Name: message_templates; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.message_templates (id, content, category, language, type, is_active, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: messages; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.messages (id, group_id, content, sent_at, status, error, is_active, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: migrations; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.migrations (id, version, applied_at) FROM stdin;
1	2.1	2025-05-01 05:09:17.739189
2	2.1	2025-05-01 06:41:48.961833
3	2.1	2025-05-01 06:45:20.280427
4	2.1	2025-05-01 06:47:20.066182
\.


--
-- Data for Name: mining_data; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.mining_data (id, user_id, username, first_name, last_name, group_id, group_name, message_count, first_seen, last_seen, is_active, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: mining_logs; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.mining_logs (id, mining_id, action_type, details, "timestamp", success, error, created_at, user_id, telegram_id) FROM stdin;
\.


--
-- Data for Name: settings; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.settings (id, key, value, created_at, updated_at) FROM stdin;
1	session_string	\N	2025-05-01 13:56:39.524893	2025-05-01 13:56:39.524893
\.


--
-- Data for Name: spam_messages; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.spam_messages (id, content, category, is_active, created_at, updated_at, created_by, language) FROM stdin;
1	Merhaba! Yeni grubumuzda sizi görmekten mutluluk duyuyoruz. Lütfen kuralları okuyun ve saygılı olun.	welcome	t	2025-04-20 19:21:50.46238	2025-04-20 19:21:50.46238	\N	tr
2	Duyuru: Grubumuzda yeni etkinlikler yakında başlayacak. Takipte kalın!	announcement	t	2025-04-20 19:21:50.507998	2025-04-20 19:21:50.507998	\N	tr
3	Grup kuralları: 1) Saygılı olun 2) Spam yapmayın 3) Uygunsuz içerik paylaşmayın	rules	t	2025-04-20 19:21:50.508593	2025-04-20 19:21:50.508593	\N	tr
\.


--
-- Data for Name: user_activity; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.user_activity (id, user_id, action, details, ip_address, created_at, session_id) FROM stdin;
\.


--
-- Data for Name: user_bio_links; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.user_bio_links (id, user_id, link_type, link_url, is_verified, group_id, discovered_at, last_checked, is_active) FROM stdin;
\.


--
-- Data for Name: user_bio_scan_logs; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.user_bio_scan_logs (id, user_id, scan_results, scanned_at) FROM stdin;
\.


--
-- Data for Name: user_demographics; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.user_demographics (id, user_id, language, bio_keywords, country, interests, profile_picture_url, last_updated, verified, premium, mutual_contact, common_chats_count, created_at, updated_at, sentiments) FROM stdin;
\.


--
-- Data for Name: user_group_activity; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.user_group_activity (id, user_id, group_id, last_seen, is_active, is_admin, message_count, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: user_group_relation; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.user_group_relation (id, user_id, group_id, is_admin, join_date, message_count, last_activity, is_active, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: user_group_relation_backup; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.user_group_relation_backup (id, user_id, group_id, is_admin, join_date, message_count, last_activity, is_active, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: user_groups; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.user_groups (id, user_id, group_id, join_date, is_admin, rank, message_count, last_message, is_active, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: user_groups_backup; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.user_groups_backup (id, user_id, group_id, join_date, is_admin, rank, message_count, last_message, is_active, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: user_invites; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.user_invites (id, user_id, username, invite_link, group_id, status, invited_at, joined_at, last_invite_date, is_active, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: users; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.users (id, user_id, username, first_name, last_name, is_active, join_date, last_seen, created_at, updated_at) FROM stdin;
\.


--
-- Name: category_groups_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.category_groups_id_seq', 1, false);


--
-- Name: data_mining_mining_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.data_mining_mining_id_seq', 1, false);


--
-- Name: debug_bot_users_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.debug_bot_users_id_seq', 1, false);


--
-- Name: group_analytics_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.group_analytics_id_seq', 1, false);


--
-- Name: groups_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.groups_id_seq', 36, true);


--
-- Name: message_templates_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.message_templates_id_seq', 1, false);


--
-- Name: messages_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.messages_id_seq', 1, false);


--
-- Name: migrations_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.migrations_id_seq', 4, true);


--
-- Name: mining_data_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.mining_data_id_seq', 1, false);


--
-- Name: mining_logs_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.mining_logs_id_seq', 1, false);


--
-- Name: settings_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.settings_id_seq', 2, true);


--
-- Name: spam_messages_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.spam_messages_id_seq', 3, true);


--
-- Name: user_activity_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.user_activity_id_seq', 1, false);


--
-- Name: user_bio_links_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.user_bio_links_id_seq', 1, false);


--
-- Name: user_bio_scan_logs_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.user_bio_scan_logs_id_seq', 1, false);


--
-- Name: user_demographics_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.user_demographics_id_seq', 1, false);


--
-- Name: user_group_activity_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.user_group_activity_id_seq', 1, false);


--
-- Name: user_group_relation_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.user_group_relation_id_seq', 1, false);


--
-- Name: user_groups_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.user_groups_id_seq', 1, false);


--
-- Name: user_invites_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.user_invites_id_seq', 1, false);


--
-- Name: users_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.users_id_seq', 1, false);


--
-- Name: category_groups category_groups_group_id_category_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.category_groups
    ADD CONSTRAINT category_groups_group_id_category_key UNIQUE (group_id, category);


--
-- Name: category_groups category_groups_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.category_groups
    ADD CONSTRAINT category_groups_pkey PRIMARY KEY (id);


--
-- Name: config config_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.config
    ADD CONSTRAINT config_pkey PRIMARY KEY (key);


--
-- Name: data_mining data_mining_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.data_mining
    ADD CONSTRAINT data_mining_pkey PRIMARY KEY (mining_id);


--
-- Name: debug_bot_users debug_bot_users_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.debug_bot_users
    ADD CONSTRAINT debug_bot_users_pkey PRIMARY KEY (id);


--
-- Name: debug_bot_users debug_bot_users_user_id_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.debug_bot_users
    ADD CONSTRAINT debug_bot_users_user_id_key UNIQUE (user_id);


--
-- Name: group_analytics group_analytics_group_id_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.group_analytics
    ADD CONSTRAINT group_analytics_group_id_key UNIQUE (group_id);


--
-- Name: group_analytics group_analytics_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.group_analytics
    ADD CONSTRAINT group_analytics_pkey PRIMARY KEY (id);


--
-- Name: groups groups_group_id_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.groups
    ADD CONSTRAINT groups_group_id_key UNIQUE (group_id);


--
-- Name: groups groups_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.groups
    ADD CONSTRAINT groups_pkey PRIMARY KEY (id);


--
-- Name: message_templates message_templates_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.message_templates
    ADD CONSTRAINT message_templates_pkey PRIMARY KEY (id);


--
-- Name: messages messages_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.messages
    ADD CONSTRAINT messages_pkey PRIMARY KEY (id);


--
-- Name: migrations migrations_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.migrations
    ADD CONSTRAINT migrations_pkey PRIMARY KEY (id);


--
-- Name: mining_data mining_data_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.mining_data
    ADD CONSTRAINT mining_data_pkey PRIMARY KEY (id);


--
-- Name: mining_logs mining_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.mining_logs
    ADD CONSTRAINT mining_logs_pkey PRIMARY KEY (id);


--
-- Name: settings settings_key_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.settings
    ADD CONSTRAINT settings_key_key UNIQUE (key);


--
-- Name: settings settings_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.settings
    ADD CONSTRAINT settings_pkey PRIMARY KEY (id);


--
-- Name: spam_messages spam_messages_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.spam_messages
    ADD CONSTRAINT spam_messages_pkey PRIMARY KEY (id);


--
-- Name: spam_messages unique_content; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.spam_messages
    ADD CONSTRAINT unique_content UNIQUE (content);


--
-- Name: user_activity user_activity_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.user_activity
    ADD CONSTRAINT user_activity_pkey PRIMARY KEY (id);


--
-- Name: user_bio_links user_bio_links_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.user_bio_links
    ADD CONSTRAINT user_bio_links_pkey PRIMARY KEY (id);


--
-- Name: user_bio_links user_bio_links_user_id_link_url_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.user_bio_links
    ADD CONSTRAINT user_bio_links_user_id_link_url_key UNIQUE (user_id, link_url);


--
-- Name: user_bio_scan_logs user_bio_scan_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.user_bio_scan_logs
    ADD CONSTRAINT user_bio_scan_logs_pkey PRIMARY KEY (id);


--
-- Name: user_demographics user_demographics_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.user_demographics
    ADD CONSTRAINT user_demographics_pkey PRIMARY KEY (id);


--
-- Name: user_demographics user_demographics_user_id_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.user_demographics
    ADD CONSTRAINT user_demographics_user_id_key UNIQUE (user_id);


--
-- Name: user_group_activity user_group_activity_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.user_group_activity
    ADD CONSTRAINT user_group_activity_pkey PRIMARY KEY (id);


--
-- Name: user_group_activity user_group_activity_user_id_group_id_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.user_group_activity
    ADD CONSTRAINT user_group_activity_user_id_group_id_key UNIQUE (user_id, group_id);


--
-- Name: user_group_relation user_group_relation_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.user_group_relation
    ADD CONSTRAINT user_group_relation_pkey PRIMARY KEY (id);


--
-- Name: user_groups user_groups_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.user_groups
    ADD CONSTRAINT user_groups_pkey PRIMARY KEY (id);


--
-- Name: user_invites user_invites_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.user_invites
    ADD CONSTRAINT user_invites_pkey PRIMARY KEY (id);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: users users_user_id_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_user_id_key UNIQUE (user_id);


--
-- Name: idx_category_groups_category; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_category_groups_category ON public.category_groups USING btree (category);


--
-- Name: idx_data_mining_user_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_data_mining_user_id ON public.data_mining USING btree (user_id);


--
-- Name: idx_groups_group_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_groups_group_id ON public.groups USING btree (group_id);


--
-- Name: idx_groups_is_active; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_groups_is_active ON public.groups USING btree (is_active);


--
-- Name: idx_message_templates_category; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_message_templates_category ON public.message_templates USING btree (category);


--
-- Name: idx_message_templates_type; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_message_templates_type ON public.message_templates USING btree (type);


--
-- Name: idx_messages_group_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_messages_group_id ON public.messages USING btree (group_id);


--
-- Name: idx_mining_data_group_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_mining_data_group_id ON public.mining_data USING btree (group_id);


--
-- Name: idx_mining_data_user_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_mining_data_user_id ON public.mining_data USING btree (user_id);


--
-- Name: idx_mining_logs_mining_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_mining_logs_mining_id ON public.mining_logs USING btree (mining_id);


--
-- Name: idx_mining_logs_telegram_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_mining_logs_telegram_id ON public.mining_logs USING btree (telegram_id);


--
-- Name: idx_mining_logs_user_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_mining_logs_user_id ON public.mining_logs USING btree (user_id);


--
-- Name: idx_settings_key; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_settings_key ON public.settings USING btree (key);


--
-- Name: idx_spam_messages_category; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_spam_messages_category ON public.spam_messages USING btree (category);


--
-- Name: idx_user_activity_created_at; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_user_activity_created_at ON public.user_activity USING btree (created_at);


--
-- Name: idx_user_activity_timestamp; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_user_activity_timestamp ON public.user_activity USING btree (created_at);


--
-- Name: idx_user_activity_user_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_user_activity_user_id ON public.user_activity USING btree (user_id);


--
-- Name: idx_user_bio_links_active; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_user_bio_links_active ON public.user_bio_links USING btree (is_active);


--
-- Name: idx_user_bio_links_type; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_user_bio_links_type ON public.user_bio_links USING btree (link_type);


--
-- Name: idx_user_bio_links_user; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_user_bio_links_user ON public.user_bio_links USING btree (user_id);


--
-- Name: idx_user_demographics_language; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_user_demographics_language ON public.user_demographics USING btree (language);


--
-- Name: idx_user_demographics_premium; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_user_demographics_premium ON public.user_demographics USING btree (premium);


--
-- Name: idx_user_demographics_verified; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_user_demographics_verified ON public.user_demographics USING btree (verified);


--
-- Name: idx_user_group_activity_active; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_user_group_activity_active ON public.user_group_activity USING btree (is_active);


--
-- Name: idx_user_group_activity_group; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_user_group_activity_group ON public.user_group_activity USING btree (group_id);


--
-- Name: idx_user_group_activity_user; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_user_group_activity_user ON public.user_group_activity USING btree (user_id);


--
-- Name: idx_user_group_relation_group_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_user_group_relation_group_id ON public.user_group_relation USING btree (group_id);


--
-- Name: idx_user_group_relation_user_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_user_group_relation_user_id ON public.user_group_relation USING btree (user_id);


--
-- Name: idx_user_groups_group_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_user_groups_group_id ON public.user_groups USING btree (group_id);


--
-- Name: idx_user_groups_user_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_user_groups_user_id ON public.user_groups USING btree (user_id);


--
-- Name: idx_user_invites_group_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_user_invites_group_id ON public.user_invites USING btree (group_id);


--
-- Name: idx_user_invites_user_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_user_invites_user_id ON public.user_invites USING btree (user_id);


--
-- Name: idx_users_is_active; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_users_is_active ON public.users USING btree (is_active);


--
-- Name: idx_users_user_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_users_user_id ON public.users USING btree (user_id);


--
-- Name: idx_users_username; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_users_username ON public.users USING btree (username);


--
-- Name: SCHEMA public; Type: ACL; Schema: -; Owner: postgres
--

REVOKE ALL ON SCHEMA public FROM siyahkare;
REVOKE ALL ON SCHEMA public FROM PUBLIC;
GRANT ALL ON SCHEMA public TO postgres;
GRANT ALL ON SCHEMA public TO PUBLIC;


--
-- Name: TABLE category_groups; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.category_groups TO PUBLIC;


--
-- Name: SEQUENCE category_groups_id_seq; Type: ACL; Schema: public; Owner: postgres
--

GRANT SELECT,USAGE ON SEQUENCE public.category_groups_id_seq TO PUBLIC;


--
-- Name: TABLE config; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.config TO PUBLIC;


--
-- Name: TABLE data_mining; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.data_mining TO PUBLIC;


--
-- Name: SEQUENCE data_mining_mining_id_seq; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON SEQUENCE public.data_mining_mining_id_seq TO PUBLIC;


--
-- Name: TABLE debug_bot_users; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.debug_bot_users TO PUBLIC;


--
-- Name: SEQUENCE debug_bot_users_id_seq; Type: ACL; Schema: public; Owner: postgres
--

GRANT SELECT,USAGE ON SEQUENCE public.debug_bot_users_id_seq TO PUBLIC;


--
-- Name: TABLE group_analytics; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.group_analytics TO PUBLIC;


--
-- Name: SEQUENCE group_analytics_id_seq; Type: ACL; Schema: public; Owner: postgres
--

GRANT SELECT,USAGE ON SEQUENCE public.group_analytics_id_seq TO PUBLIC;


--
-- Name: TABLE groups; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.groups TO PUBLIC;


--
-- Name: TABLE groups_backup; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.groups_backup TO PUBLIC;


--
-- Name: SEQUENCE groups_id_seq; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON SEQUENCE public.groups_id_seq TO PUBLIC;


--
-- Name: TABLE message_templates; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.message_templates TO PUBLIC;


--
-- Name: SEQUENCE message_templates_id_seq; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON SEQUENCE public.message_templates_id_seq TO PUBLIC;


--
-- Name: TABLE messages; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.messages TO PUBLIC;


--
-- Name: SEQUENCE messages_id_seq; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON SEQUENCE public.messages_id_seq TO PUBLIC;


--
-- Name: TABLE migrations; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.migrations TO PUBLIC;


--
-- Name: SEQUENCE migrations_id_seq; Type: ACL; Schema: public; Owner: postgres
--

GRANT SELECT,USAGE ON SEQUENCE public.migrations_id_seq TO PUBLIC;


--
-- Name: TABLE mining_data; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.mining_data TO PUBLIC;


--
-- Name: SEQUENCE mining_data_id_seq; Type: ACL; Schema: public; Owner: postgres
--

GRANT SELECT,USAGE ON SEQUENCE public.mining_data_id_seq TO PUBLIC;


--
-- Name: TABLE mining_logs; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.mining_logs TO PUBLIC;


--
-- Name: SEQUENCE mining_logs_id_seq; Type: ACL; Schema: public; Owner: postgres
--

GRANT SELECT,USAGE ON SEQUENCE public.mining_logs_id_seq TO PUBLIC;


--
-- Name: TABLE settings; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.settings TO PUBLIC;


--
-- Name: SEQUENCE settings_id_seq; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON SEQUENCE public.settings_id_seq TO PUBLIC;


--
-- Name: TABLE spam_messages; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.spam_messages TO PUBLIC;


--
-- Name: SEQUENCE spam_messages_id_seq; Type: ACL; Schema: public; Owner: postgres
--

GRANT SELECT,USAGE ON SEQUENCE public.spam_messages_id_seq TO PUBLIC;


--
-- Name: TABLE user_activity; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.user_activity TO PUBLIC;


--
-- Name: SEQUENCE user_activity_id_seq; Type: ACL; Schema: public; Owner: postgres
--

GRANT SELECT,USAGE ON SEQUENCE public.user_activity_id_seq TO PUBLIC;


--
-- Name: TABLE user_bio_links; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.user_bio_links TO PUBLIC;


--
-- Name: SEQUENCE user_bio_links_id_seq; Type: ACL; Schema: public; Owner: postgres
--

GRANT SELECT,USAGE ON SEQUENCE public.user_bio_links_id_seq TO PUBLIC;


--
-- Name: TABLE user_bio_scan_logs; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.user_bio_scan_logs TO PUBLIC;


--
-- Name: SEQUENCE user_bio_scan_logs_id_seq; Type: ACL; Schema: public; Owner: postgres
--

GRANT SELECT,USAGE ON SEQUENCE public.user_bio_scan_logs_id_seq TO PUBLIC;


--
-- Name: TABLE user_demographics; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.user_demographics TO PUBLIC;


--
-- Name: SEQUENCE user_demographics_id_seq; Type: ACL; Schema: public; Owner: postgres
--

GRANT SELECT,USAGE ON SEQUENCE public.user_demographics_id_seq TO PUBLIC;


--
-- Name: TABLE user_group_activity; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.user_group_activity TO PUBLIC;


--
-- Name: SEQUENCE user_group_activity_id_seq; Type: ACL; Schema: public; Owner: postgres
--

GRANT SELECT,USAGE ON SEQUENCE public.user_group_activity_id_seq TO PUBLIC;


--
-- Name: TABLE user_group_relation; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.user_group_relation TO PUBLIC;


--
-- Name: TABLE user_group_relation_backup; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.user_group_relation_backup TO PUBLIC;


--
-- Name: SEQUENCE user_group_relation_id_seq; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON SEQUENCE public.user_group_relation_id_seq TO PUBLIC;


--
-- Name: TABLE user_groups; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.user_groups TO PUBLIC;


--
-- Name: TABLE user_groups_backup; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.user_groups_backup TO PUBLIC;


--
-- Name: SEQUENCE user_groups_id_seq; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON SEQUENCE public.user_groups_id_seq TO PUBLIC;


--
-- Name: TABLE user_invites; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.user_invites TO PUBLIC;


--
-- Name: SEQUENCE user_invites_id_seq; Type: ACL; Schema: public; Owner: postgres
--

GRANT SELECT,USAGE ON SEQUENCE public.user_invites_id_seq TO PUBLIC;


--
-- Name: TABLE users; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.users TO PUBLIC;


--
-- Name: SEQUENCE users_id_seq; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON SEQUENCE public.users_id_seq TO PUBLIC;


--
-- Name: DEFAULT PRIVILEGES FOR SEQUENCES; Type: DEFAULT ACL; Schema: public; Owner: postgres
--

ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public GRANT ALL ON SEQUENCES  TO PUBLIC;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public GRANT ALL ON SEQUENCES  TO postgres;


--
-- Name: DEFAULT PRIVILEGES FOR TYPES; Type: DEFAULT ACL; Schema: public; Owner: postgres
--

ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public GRANT ALL ON TYPES  TO PUBLIC;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public GRANT ALL ON TYPES  TO postgres;


--
-- Name: DEFAULT PRIVILEGES FOR FUNCTIONS; Type: DEFAULT ACL; Schema: public; Owner: postgres
--

ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public GRANT ALL ON FUNCTIONS  TO PUBLIC;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public GRANT ALL ON FUNCTIONS  TO postgres;


--
-- Name: DEFAULT PRIVILEGES FOR TABLES; Type: DEFAULT ACL; Schema: public; Owner: postgres
--

ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public GRANT ALL ON TABLES  TO PUBLIC;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public GRANT ALL ON TABLES  TO postgres;


--
-- PostgreSQL database dump complete
--

