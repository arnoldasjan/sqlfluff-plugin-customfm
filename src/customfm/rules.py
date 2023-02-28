from typing import List, Type, Optional

from sqlfluff.core.plugin import hookimpl
from sqlfluff.core.parser import SymbolSegment, NewlineSegment

from sqlfluff.core.rules import BaseRule, LintFix, LintResult, RuleContext
from sqlfluff.core.rules.crawlers import SegmentSeekerCrawler
from sqlfluff.core.rules.doc_decorators import (
    document_fix_compatible,
    document_groups,
)
from sqlfluff.utils.functional import Segments, FunctionalContext, sp
import os.path
from sqlfluff.core.config import ConfigLoader


@hookimpl
def get_rules() -> List[Type[BaseRule]]:
    """Get plugin rules."""
    return [
        Rule_CustomFM_L001,
        Rule_CustomFM_L002,
        Rule_CustomFM_L003,
        Rule_CustomFM_L004,
        Rule_CustomFM_L005,
    ]


@hookimpl
def load_default_config() -> dict:
    """Loads the default configuration for the plugin."""
    return ConfigLoader.get_global().load_config_file(
        file_dir=os.path.dirname(__file__),
        file_name="plugin_default_config.cfg",
    )


@hookimpl
def get_configs_info() -> dict:
    """Get rule config validations and descriptions."""
    return {
        "keywords_to_check": {
            "definition": "A list of keywords to check blank lines for"
        },
    }


def get_newlines(
    elements: Segments, start_seg: Segments, is_reversed: bool = False
) -> Segments:
    if is_reversed:
        newlines = elements.reversed().select(
            select_if=sp.is_type("newline"),
            start_seg=start_seg[0],
            loop_while=sp.or_(sp.is_whitespace(), sp.is_meta()),
        )
    else:
        newlines = elements.select(
            select_if=sp.is_type("newline"),
            start_seg=start_seg[0],
            loop_while=sp.or_(sp.is_whitespace(), sp.is_meta(), sp.is_type("comma")),
        )

    return newlines


def get_elements_to_delete(
    elements: Segments, start_seg: Segments, is_reversed: bool = False
) -> Segments:
    if is_reversed:
        elements_to_delete = elements.reversed().select(
            start_seg=start_seg[0],
            loop_while=sp.or_(sp.is_whitespace(), sp.is_type("newline"), sp.is_meta()),
        )
    else:
        elements_to_delete = elements.select(
            start_seg=start_seg[0],
            loop_while=sp.or_(
                sp.is_whitespace(),
                sp.is_type("newline"),
                sp.is_meta(),
                sp.is_type("comma"),
            ),
        )
    return elements_to_delete


@document_groups
@document_fix_compatible
class Rule_CustomFM_L001(BaseRule):
    """There should be a blank line before SQL keywords (from, where etc.)

    **Anti-pattern**

    Not having blank line before FROM clause.

    .. code-block:: sql

        SELECT *
        FROM foo

    **Best practice**

    Have blank line before FROM.

    .. code-block:: sql

        SELECT *

        FROM foo
    """

    groups = ("all", "core")
    crawl_behaviour = SegmentSeekerCrawler(
        {"from_clause", "where_clause", "groupby_clause", "orderby_clause"}
    )

    def _eval(self, context: RuleContext) -> Optional[List[LintResult]]:
        """Blank line expected but not found before keyword (select, from etc.) clause."""
        error_buffer = []
        fixes = []
        seg = Segments(context.segment)
        parent_seg = Segments(context.parent_stack[-1])

        if not parent_seg[0].is_type("window_specification"):
            children = Segments(context.parent_stack[-1]).children()

            newlines_before = get_newlines(
                elements=children, start_seg=seg, is_reversed=True
            )

            newlines_count = len(newlines_before)

            if newlines_count != 2:
                first_not_meta_element = (
                    children.reversed()
                    .select(
                        select_if=sp.not_(sp.is_meta()),
                        start_seg=seg[0],
                    )
                    .first()
                )

                if newlines_count < 2:
                    fixes.append(
                        LintFix.create_before(
                            anchor_segment=first_not_meta_element[0],
                            edit_segments=[NewlineSegment()] * (2 - newlines_count),
                        )
                    )

                else:
                    ws_to_delete = get_elements_to_delete(
                        elements=children,
                        start_seg=first_not_meta_element,
                        is_reversed=True,
                    )

                    fixes.extend([LintFix.delete(ws) for ws in ws_to_delete])
                    fixes.append(
                        LintFix.create_before(
                            anchor_segment=first_not_meta_element[0],
                            edit_segments=[NewlineSegment()] * 2,
                        )
                    )

        if fixes:
            error_buffer.append(LintResult(anchor=seg[0], fixes=fixes))

        return error_buffer or None


@document_groups
@document_fix_compatible
class Rule_CustomFM_L002(BaseRule):
    """Join clause keywords (ON, AND) should start from new line

    **Anti-pattern**

    Writing join clause in the same line

    .. code-block:: sql

        SELECT * FROM foo
        LEFT JOIN b ON b.id = foo.id

    **Best practice**

    Join ON condition starts in a new line

    .. code-block:: sql

        SELECT * FROM foo
        LEFT JOIN b
            ON b.id = foo.id
    """

    groups = ("all",)
    crawl_behaviour = SegmentSeekerCrawler({"join_clause"})

    def _eval(self, context: RuleContext) -> Optional[List[LintResult]]:
        """Join clause keywords (ON, AND) are not in a new line"""
        error_buffer = []

        assert context.segment.is_type("join_clause")
        children = FunctionalContext(context).segment.children()

        fixes = []

        join_condition = children.first(sp.is_type("join_on_condition"))

        if join_condition:
            newlines = children.reversed().select(
                select_if=sp.is_type("newline"),
                start_seg=join_condition[0],
                loop_while=sp.or_(sp.is_whitespace(), sp.is_meta()),
            )

            if len(newlines) != 1:
                ws_to_delete = children.reversed().select(
                    start_seg=join_condition[0],
                    loop_while=sp.or_(
                        sp.is_whitespace(), sp.is_type("newline"), sp.is_meta()
                    ),
                )

                fixes.extend([LintFix.delete(ws) for ws in ws_to_delete])
                fixes.append(
                    LintFix.create_before(
                        anchor_segment=join_condition[0],
                        edit_segments=[NewlineSegment()],
                    )
                )

            join_condition_expression = join_condition.children().first(
                sp.is_type("expression")
            )
            binary_segs = join_condition_expression.children(
                sp.is_type("binary_operator")
            )

            if binary_segs:
                for binary_seg in binary_segs:
                    bs_newlines = (
                        join_condition_expression.children()
                        .reversed()
                        .select(
                            select_if=sp.is_type("newline"),
                            start_seg=binary_seg,
                            loop_while=sp.or_(sp.is_whitespace(), sp.is_meta()),
                        )
                    )

                    if len(bs_newlines) != 1:
                        bs_ws_to_delete = (
                            join_condition_expression.children()
                            .reversed()
                            .select(
                                start_seg=binary_seg,
                                loop_while=sp.or_(
                                    sp.is_whitespace(),
                                    sp.is_type("newline"),
                                    sp.is_meta(),
                                ),
                            )
                        )

                        fixes.extend(
                            [LintFix.delete(bs_ws) for bs_ws in bs_ws_to_delete]
                        )
                        fixes.append(
                            LintFix.create_before(
                                anchor_segment=binary_seg,
                                edit_segments=[NewlineSegment()],
                            )
                        )

            if fixes:
                error_buffer.append(LintResult(join_condition[0], fixes=fixes))

        return error_buffer or None


@document_groups
@document_fix_compatible
class Rule_CustomFM_L003(BaseRule):
    """Case when expressions should have blank line before and after, keywords start in new line

    **Anti-pattern**

    Case when expression without extra lines

    .. code-block:: sql

        SELECT
            a,
            case when true then 1 end,
            b
        FROM foo

    **Best practice**

    Case when expression has blank line before and after

    .. code-block:: sql

        SELECT
            a,

            case when true then 1 end,

            b
        FROM foo
    """

    groups = ("all",)
    crawl_behaviour = SegmentSeekerCrawler({"select_clause"})

    def _eval(self, context: RuleContext) -> Optional[List[LintResult]]:
        """Case when expressions should be separated by blank lines"""
        error_buffer = []
        fixes = []

        assert context.segment.is_type("select_clause")
        children = FunctionalContext(context).segment.children()
        select_clause_elements = FunctionalContext(context).segment.children(
            sp.is_type("select_clause_element")
        )

        for element in select_clause_elements.iterate_segments():
            element_case_expr = element.children(sp.is_type("expression")).children(
                sp.is_type("case_expression")
            )

            if element_case_expr:
                newlines_before = get_newlines(
                    elements=children, start_seg=element, is_reversed=True
                )
                newlines_after = get_newlines(
                    elements=children, start_seg=element, is_reversed=False
                )

                if len(newlines_before) != 2:
                    ws_to_delete = get_elements_to_delete(
                        children, element, is_reversed=True
                    )

                    fixes.extend([LintFix.delete(ws) for ws in ws_to_delete])
                    fixes.append(
                        LintFix.create_before(
                            anchor_segment=element[0],
                            edit_segments=[NewlineSegment()] * 2,
                        )
                    )

                if len(newlines_after) != 2:
                    ws_to_delete = get_elements_to_delete(
                        children, element, is_reversed=False
                    )

                    fixes.extend([LintFix.delete(ws) for ws in ws_to_delete])
                    fixes.append(
                        LintFix.create_after(
                            anchor_segment=element[0],
                            edit_segments=[
                                SymbolSegment(",", type="comma"),
                                NewlineSegment(),
                                NewlineSegment(),
                            ],
                        )
                    )

                when_clauses = element_case_expr.children(
                    sp.or_(
                        sp.is_type("when_clause"),
                        sp.is_type("else_clause"),
                        sp.is_keyword("end"),
                    )
                )
                case_expr_children = element_case_expr.children()

                for when_clause in when_clauses.iterate_segments():
                    newlines_before_when = get_newlines(
                        elements=case_expr_children,
                        start_seg=when_clause,
                        is_reversed=True,
                    )

                    if len(newlines_before_when) != 1:
                        ws_to_delete = get_elements_to_delete(
                            case_expr_children, when_clause, is_reversed=True
                        )

                        fixes.extend([LintFix.delete(ws) for ws in ws_to_delete])
                        fixes.append(
                            LintFix.create_before(
                                anchor_segment=when_clause[0],
                                edit_segments=[NewlineSegment()],
                            )
                        )

                    then_clause = when_clause.children(sp.is_keyword("then"))
                    when_clause_children = when_clause.children()

                    if then_clause:
                        newlines_before_then = get_newlines(
                            when_clause_children, then_clause, is_reversed=True
                        )
                        if len(newlines_before_then) != 1:
                            ws_to_delete = get_elements_to_delete(
                                when_clause_children, then_clause, is_reversed=True
                            )

                            fixes.extend([LintFix.delete(ws) for ws in ws_to_delete])
                            fixes.append(
                                LintFix.create_before(
                                    anchor_segment=then_clause[0],
                                    edit_segments=[NewlineSegment()],
                                )
                            )

            if fixes:
                error_buffer.append(LintResult(element[0], fixes=fixes))
                fixes = []

        return error_buffer or None


@document_groups
@document_fix_compatible
class Rule_CustomFM_L004(BaseRule):
    """Keywords in separate lines inside window functions

    **Anti-pattern**

    Row number function with inline keywords

    .. code-block:: sql

        SELECT
            a,
            row_number() over (partition by a order by b desc) as rn,
            b
        FROM foo

    **Best practice**

    Row number function in separate lines

    .. code-block:: sql

        SELECT
            a,
            row_number() over (
                partition by a
                order by b desc
            ) as rn,
            b
        FROM foo
    """

    groups = ("all",)
    crawl_behaviour = SegmentSeekerCrawler({"window_specification"})

    def _eval(self, context: RuleContext) -> Optional[List[LintResult]]:
        """Keywords in separate lines inside window functions"""
        error_buffer = []
        fixes = []

        assert context.segment.is_type("window_specification")
        window_spec_children = FunctionalContext(context).segment.children()
        window_spec = FunctionalContext(context).segment
        upper_seg = Segments(context.parent_stack[-1])

        newlines_before = len(
            get_newlines(
                elements=upper_seg.children(), start_seg=window_spec, is_reversed=True
            )
        )
        newlines_after = len(
            get_newlines(
                elements=upper_seg.children(), start_seg=window_spec, is_reversed=False
            )
        )

        if newlines_before != 1:
            meta_element = (
                upper_seg.children()
                .reversed()
                .select(
                    select_if=sp.is_meta(),
                    start_seg=window_spec[0],
                )
                .first()
            )

            if newlines_before < 1:
                fixes.append(
                    LintFix.create_before(
                        anchor_segment=meta_element[0], edit_segments=[NewlineSegment()]
                    )
                )

            else:
                ws_to_delete = get_elements_to_delete(
                    elements=upper_seg.children(),
                    start_seg=meta_element,
                    is_reversed=True,
                )

                fixes.extend([LintFix.delete(ws) for ws in ws_to_delete])
                fixes.append(
                    LintFix.create_before(
                        anchor_segment=meta_element[0], edit_segments=[NewlineSegment()]
                    )
                )

        if newlines_after != 1:
            meta_element = (
                upper_seg.children()
                .select(
                    select_if=sp.is_meta(),
                    start_seg=window_spec[0],
                )
                .first()
            )

            if newlines_after < 1:
                fixes.append(
                    LintFix.create_after(
                        anchor_segment=meta_element[0], edit_segments=[NewlineSegment()]
                    )
                )

            else:
                ws_to_delete = get_elements_to_delete(
                    elements=upper_seg.children(),
                    start_seg=meta_element,
                    is_reversed=False,
                )

                fixes.extend([LintFix.delete(ws) for ws in ws_to_delete])
                fixes.append(
                    LintFix.create_after(
                        anchor_segment=meta_element[0], edit_segments=[NewlineSegment()]
                    )
                )

        orderby = window_spec.children(sp.is_type("orderby_clause"))

        if orderby:
            newlines_before_orderby = len(
                get_newlines(
                    elements=window_spec_children, start_seg=orderby, is_reversed=True
                )
            )

            if newlines_before_orderby != 1:
                if newlines_before_orderby < 1:
                    fixes.append(
                        LintFix.create_before(
                            anchor_segment=orderby[0], edit_segments=[NewlineSegment()]
                        )
                    )

                else:
                    ws_to_delete = get_elements_to_delete(
                        elements=window_spec_children,
                        start_seg=orderby,
                        is_reversed=True,
                    )

                    fixes.extend([LintFix.delete(ws) for ws in ws_to_delete])
                    fixes.append(
                        LintFix.create_before(
                            anchor_segment=orderby[0], edit_segments=[NewlineSegment()]
                        )
                    )

        if fixes:
            error_buffer.append(LintResult(anchor=window_spec[0], fixes=fixes))

        return error_buffer or None


@document_groups
class Rule_CustomFM_L005(BaseRule):
    """Last line should always include a select * from

    **Anti-pattern**

    Multiple elements are selected in the last line

    .. code-block:: sql

        SELECT
            a,
            b,
            c
        FROM foo

    **Best practice**

    Only select * from in the last line

    .. code-block:: sql

        select * from foo
    """

    groups = ("all",)
    crawl_behaviour = SegmentSeekerCrawler({"with_compound_statement"})

    def _eval(self, context: RuleContext):
        error_buffer = []
        assert context.segment.is_type("with_compound_statement")
        select_clause = (
            FunctionalContext(context)
            .segment.children(sp.is_type("select_statement"))
            .children(sp.is_type("select_clause"))
        )
        select_elements = select_clause.children(sp.is_type("select_clause_element"))

        if len(select_elements) > 1:
            error_buffer.append(
                LintResult(
                    anchor=select_clause[0],
                    description="Multiple select elements found",
                )
            )

        else:
            wildcard = select_elements.children(sp.is_type("wildcard_expression"))
            if len(wildcard) != 1:
                error_buffer.append(
                    LintResult(
                        anchor=select_clause[0],
                        description="Only element should be wildcard",
                    )
                )

        return error_buffer or None
