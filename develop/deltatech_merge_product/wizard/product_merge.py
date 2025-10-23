# © 2008-2021 Deltatech
# Rewritten for Odoo 17 compatibility

import datetime
import functools
import itertools
import logging
import psycopg2
from ast import literal_eval

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import mute_logger

_logger = logging.getLogger("merge.object")


class MergeDummy(models.TransientModel):
    _name = "merge.dummy"
    _description = "Merge Object Dummy"

    name = fields.Char()


class MergeObjectLine(models.TransientModel):
    _name = "merge.object.line"
    _description = "Merge Object Line"
    _order = "min_id asc"

    wizard_id = fields.Many2one("merge.object.wizard", "Wizard")
    min_id = fields.Integer("MinID")
    aggr_ids = fields.Char("Ids", required=True)


class MergeObject(models.TransientModel):
    _name = "merge.object.wizard"
    _description = "Merge Object Wizard"
    _model_merge = "merge.dummy"
    _table_merge = "merge_dummy"

    group_by_name = fields.Boolean("Name")

    state = fields.Selection(
        [("option", "Option"), ("selection", "Selection"), ("finished", "Finished")],
        readonly=True,
        required=True,
        default="option",
    )

    number_group = fields.Integer("Group of Objects", readonly=True)
    current_line_id = fields.Many2one("merge.object.line", string="Current Line")
    line_ids = fields.One2many("merge.object.line", "wizard_id", string="Lines")
    object_ids = fields.Many2many(_model_merge, string="Objects")
    dst_object_id = fields.Many2one(_model_merge, string="Destination Object")
    maximum_group = fields.Integer("Maximum of Group of Objects")

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        active_ids = self.env.context.get("active_ids")
        if self.env.context.get("active_model") == self._model_merge and active_ids:
            res["state"] = "selection"
            res["object_ids"] = [(6, 0, active_ids)]
            res["dst_object_id"] = self._get_ordered_object(active_ids)[-1].id
        return res

    # ----------------------------------------
    # Core Merge Methods
    # ----------------------------------------

    def _get_fk_on(self, table):
        """Return all foreign keys pointing to the given table."""
        query = """
            SELECT cl1.relname as table, att1.attname as column
            FROM pg_constraint as con, pg_class as cl1, pg_class as cl2,
                 pg_attribute as att1, pg_attribute as att2
            WHERE con.conrelid = cl1.oid
                AND con.confrelid = cl2.oid
                AND array_lower(con.conkey, 1) = 1
                AND con.conkey[1] = att1.attnum
                AND att1.attrelid = cl1.oid
                AND cl2.relname = %s
                AND att2.attname = 'id'
                AND array_lower(con.confkey, 1) = 1
                AND con.confkey[1] = att2.attnum
                AND att2.attrelid = cl2.oid
                AND con.contype = 'f'
        """
        self._cr.execute(query, (table,))
        return self._cr.fetchall()

    @api.model
    def _update_foreign_keys(self, src_objects, dst_object):
        """Update all Many2one foreign keys from src_objects to dst_object."""
        _logger.debug(
            "_update_foreign_keys for dst_object: %s for src_objects: %s",
            dst_object.id, str(src_objects.ids)
        )

        Object = self.env[self._model_merge]
        relations = self._get_fk_on(self._table_merge)
        self.env.flush_all()

        for table, column in relations:
            if "merge_object_" in table:
                continue

            self._cr.execute(
                "SELECT column_name FROM information_schema.columns WHERE table_name = %s",
                (table,)
            )
            columns = [col[0] for col in self._cr.fetchall() if col[0] != column]
            query_dic = {"table": table, "column": column, "value": columns[0] if columns else "id"}

            try:
                with mute_logger("odoo.sql_db"), self.env.cr.savepoint():
                    query = 'UPDATE "%(table)s" SET "%(column)s" = %%s WHERE "%(column)s" IN %%s' % query_dic
                    self._cr.execute(query, (dst_object.id, tuple(src_objects.ids)))
                    if column == Object._parent_name and table == self._table_merge:
                        self._cr.execute(
                            """
                            WITH RECURSIVE cycle(id, parent_id) AS (
                                SELECT id, parent_id FROM %(table)s
                                UNION
                                SELECT cycle.id, %(table)s.parent_id
                                FROM %(table)s, cycle
                                WHERE %(table)s.id = cycle.parent_id
                                  AND cycle.id != cycle.parent_id
                            )
                            SELECT id FROM cycle WHERE id = parent_id AND id = %%s
                            """ % query_dic,
                            (dst_object.id,)
                        )
            except psycopg2.Error:
                query = 'DELETE FROM "%(table)s" WHERE "%(column)s" IN %%s' % query_dic
                self._cr.execute(query, (tuple(src_objects.ids),))

        self.invalidate_recordset()

    @api.model
    def _update_reference_fields(self, src_objects, dst_object):
        """Update all reference fields pointing to src_objects."""
        _logger.debug(
            "_update_reference_fields for dst_object: %s for src_objects: %r",
            dst_object.id, src_objects.ids
        )

        def update_records(model, src, field_model="model", field_id="res_id"):
            Model = self.env.get(model)
            if not Model:
                return
            records = Model.sudo().search([(field_model, "=", self._model_merge), (field_id, "=", src.id)])
            try:
                with mute_logger("odoo.sql_db"), self.env.cr.savepoint():
                    records.sudo().write({field_id: dst_object.id})
                    self.env.flush_all()
            except psycopg2.Error:
                records.sudo().unlink()

        for src_object in src_objects:
            update_records("calendar.event", src_object, field_model="res_model")
            update_records("ir.attachment", src_object, field_model="res_model")
            update_records("mail.followers", src_object, field_model="res_model")
            update_records("portal.share", src_object, field_model="res_model")
            update_records("rating.rating", src_object, field_model="res_model")
            update_records("mail.activity", src_object, field_model="res_model")
            update_records("mail.message", src_object)
            update_records("ir.model.data", src_object)

        for record in self.env["ir.model.fields"].sudo().search([("ttype", "=", "reference")]):
            try:
                Model = self.env[record.model]
                field = Model._fields[record.name]
            except KeyError:
                continue
            if field.compute:
                continue
            for src_object in src_objects:
                records_ref = Model.sudo().search([(record.name, "=", "%s,%d" % (self._model_merge, src_object.id))])
                records_ref.sudo().write({record.name: "%s,%d" % (self._model_merge, dst_object.id)})

        self.env.flush_all()

    def _get_summable_fields(self):
        return []

    @api.model
    def _update_values(self, src_objects, dst_object):
        """Update destination object values with data from source objects."""
        _logger.debug("_update_values for dst_object: %s for src_objects: %r", dst_object.id, src_objects.ids)
        model_fields = dst_object.fields_get().keys()
        summable_fields = self._get_summable_fields()

        def write_serializer(item):
            return item.id if isinstance(item, models.BaseModel) else item

        values = {}
        for column in model_fields:
            field = dst_object._fields[column]
            if field.type not in ("many2many", "one2many") and field.compute is None:
                for item in itertools.chain(src_objects, [dst_object]):
                    if item[column]:
                        if column in summable_fields and values.get(column):
                            values[column] += write_serializer(item[column])
                        else:
                            values[column] = write_serializer(item[column])

        values.pop("id", None)
        parent_id = values.pop("parent_id", None)
        dst_object.write(values)
        if parent_id and parent_id != dst_object.id:
            try:
                dst_object.write({"parent_id": parent_id})
            except ValidationError:
                _logger.info("Skip recursive parent_id %s for object %s", parent_id, dst_object.id)

    def _merge(self, object_ids, dst_object=None, extra_checks=True):
        Object = self.env[self._model_merge]
        object_ids = Object.browse(object_ids).exists()
        if len(object_ids) < 2:
            return

        max_no_objects = int(self.env["ir.config_parameter"].sudo().get_param(
            "deltatech_merge.merge_objects_max_number", default=3
        ))

        if len(object_ids) > max_no_objects:
            raise UserError(_("You cannot merge more than %s objects together.") % max_no_objects)

        if "parent_id" in Object._fields:
            child_ids = self.env[self._model_merge]
            for object_id in object_ids:
                child_ids |= Object.search([("id", "child_of", [object_id.id])]) - object_id
            if object_ids & child_ids:
                raise UserError(_("You cannot merge an object with one of its parent."))

        if dst_object and dst_object in object_ids:
            src_objects = object_ids - dst_object
        else:
            ordered_objects = self._get_ordered_object(object_ids.ids)
            dst_object = ordered_objects[-1]
            src_objects = ordered_objects[:-1]

        _logger.info("Merging objects %s into %s", src_objects.ids, dst_object.id)
        self._update_foreign_keys(src_objects, dst_object)
        self._update_reference_fields(src_objects, dst_object)
        self._update_values(src_objects, dst_object)
        self._log_merge_operation(src_objects, dst_object)
        src_objects.unlink()

    def _log_merge_operation(self, src_objects, dst_object):
        _logger.info("(uid=%s) merged objects %r into %s", self._uid, src_objects.ids, dst_object.id)

    @api.model
    def _get_ordered_object(self, object_ids):
        return self.env[self._model_merge].browse(object_ids).sorted(
            key=lambda p: (p.create_date or datetime.datetime(1970, 1, 1)),
            reverse=True,
        )

    def action_skip(self):
        if self.current_line_id:
            self.current_line_id.unlink()
        return self._action_next_screen()

    def _action_next_screen(self):
        self.invalidate_recordset()
        values = {}
        if self.line_ids:
            current_line = self.line_ids[0]
            current_object_ids = literal_eval(current_line.aggr_ids)
            values.update({
                "current_line_id": current_line.id,
                "object_ids": [(6, 0, current_object_ids)],
                "dst_object_id": self._get_ordered_object(current_object_ids)[-1].id,
                "state": "selection",
            })
        else:
            values.update({"current_line_id": False, "object_ids": [], "state": "finished"})
        self.write(values)
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_merge(self):
        if not self.object_ids:
            self.write({"state": "finished"})
            return {
                "type": "ir.actions.act_window",
                "res_model": self._name,
                "res_id": self.id,
                "view_mode": "form",
                "target": "new",
            }

        self._merge(self.object_ids.ids, self.dst_object_id)
        if self.current_line_id:
            self.current_line_id.unlink()
        return self._action_next_screen()
