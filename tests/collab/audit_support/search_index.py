"""Independent native FTS semantic rebuild; never change the observed database."""
from __future__ import annotations
import sqlite3

from .facts import require


FTS_TABLES=frozenset({"issues_fts","issues_fts_config","issues_fts_data",
                      "issues_fts_docsize","issues_fts_idx"})
FTS_DDL="""CREATE VIRTUAL TABLE issues_fts USING fts5(
  title, body, comments,
  content='', tokenize='unicode61 remove_diacritics 2'
)"""


def sql_value(value):
    """Preserve SQL BLOB identity explicitly in the reopened raw table facts."""
    return {"sqlite_blob_hex":value.hex()} if isinstance(value,bytes) else value


def index_facts(connection, *, database="main"):
    require(database in {"main"},"Unadmitted index database")
    connection.execute("PRAGMA temp_store=MEMORY")
    connection.execute("CREATE VIRTUAL TABLE temp.a49_index_instances "
                       "USING fts5vocab(main,issues_fts,instance)")
    instances=[list(row) for row in connection.execute(
        "SELECT term,doc,col,offset FROM temp.a49_index_instances ORDER BY term,doc,col,offset")]
    documents=[row[0] for row in connection.execute("SELECT rowid FROM issues_fts ORDER BY rowid")]
    sizes=[[row[0],row[1].lower()] for row in connection.execute(
        "SELECT id,hex(sz) FROM issues_fts_docsize ORDER BY id")]
    config=[list(row) for row in connection.execute("SELECT k,v FROM issues_fts_config ORDER BY k")]
    return {"documents":documents,"instances":instances,"document_sizes":sizes,"config":config}


def check_search_index(connection, schema, issues, comments):
    names={row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    # Minimal component fixtures may omit FTS. Actual live schema admission
    # separately requires the complete installed native schema.
    related={name for name in names if "fts" in name.lower()}
    if not related:
        return None
    require(related==FTS_TABLES,"Unknown or incomplete native search-table closure")
    normalize=lambda value:"".join(value.split()).lower()
    require(normalize(schema["issues_fts"])==normalize(FTS_DDL),"Unadmitted native FTS definition")
    known={issue["id"] for issue in issues}
    require(len(known)==len(issues) and all(type(identity) is int for identity in known),
            "Duplicate/invalid issue identity for search rebuild")
    require(all(comment["issue_id"] in known and type(comment["id"]) is int and
                isinstance(comment["body"],str) for comment in comments),
            "Search comments contain an orphan or invalid native text")
    rebuilt=sqlite3.connect(":memory:")
    try:
        rebuilt.execute(FTS_DDL)
        for issue in sorted(issues,key=lambda row:row["id"]):
            require(isinstance(issue["title"],str) and isinstance(issue["body"],str),
                    "Search issue text is not native text")
            bodies=[comment["body"] for comment in sorted(comments,key=lambda row:row["id"])
                    if comment["issue_id"]==issue["id"]]
            rebuilt.execute("INSERT INTO issues_fts(rowid,title,body,comments) VALUES(?,?,?,?)",
                (issue["id"],issue["title"],issue["body"]," ".join(bodies)))
        expected=index_facts(rebuilt)
        actual=index_facts(connection)
        require(actual==expected,"Native searchable postings/document/config closure differs from issue/comment text")
        # FTS's internal integrity command executes solely in an owned memory
        # copy, never on the retained source or its WAL/SHM sidecars.
        private=sqlite3.connect(":memory:")
        try:
            connection.backup(private)
            private.execute("INSERT INTO issues_fts(issues_fts) VALUES('integrity-check')")
        finally:
            private.close()
        return actual
    finally:
        rebuilt.close()


def check_physical_search_closure(restored, independently_recovered):
    """Compare current rows, including historical payload invisible to search.

    A native fresh import commits index segments differently from a one-shot
    semantic rebuild. Its independently executed reconstruction is therefore
    the physical reference; neither repair nor optimization is an oracle.
    """
    if restored['search_index'] is None:
        require(not FTS_TABLES.intersection(restored['tables']),
                'Partial physical native search closure')
        return
    require(independently_recovered is not None,
            'Independent fresh native reconstruction required for physical search closure')
    require(restored['sql_schema']==independently_recovered['sql_schema'],
            'Native reconstruction schema differs')
    def text_ownership(database):
        return {'issues':sorted([row['id'],row['uid'],row['title'],row['body']]
                               for row in database['issues']),
                'comments':sorted([row['id'],row['issue_id'],row['body']]
                                 for row in database['tables'].get('comments',[]))}
    require(text_ownership(restored)==text_ownership(independently_recovered),
            'Native reconstruction search text/document ownership differs')
    require(restored['search_index']==independently_recovered['search_index'],
            'Native reconstruction active search semantics differ')
    require(all(restored['tables'][table]==independently_recovered['tables'][table]
                for table in FTS_TABLES),
            'Current native FTS shadow payload differs from independent fresh scoped recovery')
