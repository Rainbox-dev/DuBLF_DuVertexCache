# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTIBILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

bl_info = {
    "name" : "DuVertexCache",
    "author" : "Nicolas 'Duduf' Dufresne",
    "blender" : (2, 82, 0),
    "version" : (0, 0, 1),
    "location" : "3D View > Object > Animation menu > Create Vertex Cache",
    "description" : "An easy tool to export vertex cache / simplify scene / re-import vertex cache.",
    #"warning" : "This addon needs the \"Export Pointcache Format (.pc2)\" to be activated",
    "category" : "Animation",
    "wiki_url": "http://duvertexcache-docs.rainboxlab.org/"
}

import bpy # pylint: disable=import-error
import addon_utils # pylint: disable=import-error

from pathlib import Path
import os

from . import (
    dublf,
)

class DUVERTEXCACHE_OT_create_vertex_cache ( bpy.types.Operator ):
    """Exports a point cache of the selected objects, removes their modifiers and imports back the cache with a new Mesh Cache modifier.
    Settings can be adjusted in the Properties > Object panel."""
    bl_idname = "duvertexcache.create_vertex_cache"
    bl_label = "Create Vertex Cache"
    bl_options = {'REGISTER','UNDO'}

    world_space: bpy.props.BoolProperty(
        name="Export into World Space",
        description="Transform the Vertex coordinates into World Space",
        default=True,)
    sampling: bpy.props.EnumProperty(
        name='Sampling',
        description='Sampling --> frames per sample (0.1 yields 10 samples per frame)',
        items=(('0.01', '0.01', ''),
               ('0.05', '0.05', ''),
               ('0.1', '0.1', ''),
               ('0.2', '0.2', ''),
               ('0.25', '0.25', ''),
               ('0.5', '0.5', ''),
               ('1', '1', ''),
               ('2', '2', ''),
               ('3', '3', ''),
               ('4', '4', ''),
               ('5', '5', ''),
               ('10', '10', ''),
               ),
        default='1',)
    apply_subsurf: bpy.props.BoolProperty(
        name="Apply Subdivision Surface",
        description="Applies the subdivision before exporting cache, instead of keeping the modifier",
        default = False )

    @classmethod
    def poll(self, context):
        # temporarily enable pc2 addon if not enabled yet
        if not dublf.DuBLF_addons.is_addon_enabled('io_export_pc2'):
            return False
        obj = context.active_object
        return (
            obj is not None
            and obj.type in {'MESH', 'CURVE', 'SURFACE', 'FONT'}
        )

    def invoke( self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        lay = self.layout
        col = lay.column()
        col.prop(self, 'world_space')
        col.prop(self, 'apply_subsurf')
        col.prop(self, 'sampling')

    def execute( self, context ):
        print("\n___VERTEX CACHE___")
        # get object(s)
        objs = context.selected_objects

        if len(objs) == 0:
            return {'CANCELLED'}

        # get file path (and create cache dir if not already there)
        blend_filepath = bpy.data.filepath
        blend_dir = os.path.dirname(blend_filepath)
        blend_file = bpy.path.basename(blend_filepath)
        blend_name = os.path.splitext(blend_file)[0]
        # create cache dir
        cache_dir = blend_dir + "/" + blend_name + "_VertexCache/" + context.scene.name
        cache_dirObj = Path(cache_dir)
        try:
            cache_dirObj.mkdir(parents = True, exist_ok=True)
            # print('Vertex Cache will be saved in "' + cache_dir + '"')
        except:
            print('Cannot create directory for Vertex Cache at "' + cache_dir + '"')
            return {'CANCELLED'}
        
        for obj in objs:
            if not obj.type in {'MESH', 'CURVE', 'SURFACE', 'FONT'}:
                continue

            context_override = context.copy()
            context_override['selected_objects'] = [obj]
            context_override['active_object'] = obj
            context_override['object'] = obj
            
            print('Caching ' + context_override['active_object'].name)
            print(context_override['selected_objects'])

            # pc2 file
            pc2_file = cache_dir + "/" + obj.name + "_Cache.pc2"

            # save and remove subdivision
            subsurfs = []
            if not self.apply_subsurf:
                subsurfs = dublf.modifiers.collect_modifiers( obj, modifier_type = 'SUBSURF', remove = True )
        
            # Export Cache
            if not bpy.ops.export_shape.pc2.poll(context_override):
                print('Cannot export to Point Cache (pc2) file.')
                return {'CANCELLED'}
            bpy.ops.export_shape.pc2(
                context_override,
                rot_x90 = False,
                world_space = self.world_space,
                apply_modifiers = True,
                range_start= context.scene.frame_start,
                range_end = context.scene.frame_end,
                sampling = self.sampling,
                filepath = pc2_file)

            # apply all modifiers to object(s) 
            # We need to apply and not just remove to keep vertex count.
            # They will be overriden by the mesh cache anyway
            bpy.ops.object.modifiers_apply_all(context_override, apply_as='DATA') # This operator is registered by DuBLF
            
            # remove animation if world space only (for now)
            if (self.world_space):
                dublf.animation.remove_keyframes_from_object( obj )

            # if world space, unparent and reset object transform
            if (self.world_space):
                obj.parent = None
                dublf.animation.reset_transform(obj)

            # add Mesh Cache
            cacheMod = obj.modifiers.new("Mesh Cache (DuVertexCache)", 'MESH_CACHE')
            cacheMod.cache_format = 'PC2'
            cacheMod.filepath = pc2_file

            # restore subsurfs
            if not self.apply_subsurf:
                for subsurf in subsurfs:
                    subsurfMod = obj.modifiers.new( subsurf['name'], 'SUBSURF')
                    subsurfMod.subdivision_type = subsurf['subdivision_type']
                    subsurfMod.render_levels = subsurf['render_levels']
                    subsurfMod.levels = subsurf['levels']
                    subsurfMod.quality = subsurf['quality']
                    subsurfMod.uv_smooth = subsurf['uv_smooth']
                    subsurfMod.show_only_control_edges = subsurf['show_only_control_edges']
                    subsurfMod.use_creases = subsurf['use_creases']

            print(obj.name + " is cached!")

        # keep track of armatures if any, check if they're still used, and if not remove them from the scene (both proxies and then originals if settings tells to remove linked armatures)

        # add Mesh Cache modifier on all objects, move at first position on the stack (above remaining subdivs)
        return {'FINISHED'}

def menu_func(self, context):
    op = self.layout.operator('duvertexcache.create_vertex_cache', icon = 'PACKAGE')
    op.activeObjectOnly = False
    op.apply_subsurf = False
    op.world_space = True

classes = (
    DUVERTEXCACHE_OT_create_vertex_cache,
)

def register():
    dublf.register()
    # register
    for cls in classes:
        bpy.utils.register_class(cls)

    # menus
    bpy.types.VIEW3D_MT_object_animation.append(menu_func)

def unregister():
    dublf.unregister()
    # unregister
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

    # menu
    bpy.types.VIEW3D_MT_object_animation.remove(menu_func)
