#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import webapp2
from webapp2_extras import jinja2
from google.appengine.ext import ndb
import blob_files
import blob_serve
import markdown
import logging
import os

README = os.path.join(os.path.dirname(__file__), 'README.md')


class BaseHandler(webapp2.RequestHandler):

    def handle_exception(self, exception, debug):

        logging.exception(exception)
        self.response.write('<h3>An error occurred.</h3>')

        if isinstance(exception, webapp2.HTTPException):
            self.response.set_status(exception.code)
        else:
            self.response.set_status(500)

    @webapp2.cached_property
    def jinja2(self):
        return jinja2.get_jinja2(app=self.app)

    def render_template(self, template, **template_args):
        self.response.write(self.jinja2.render_template(template, **template_args))


class BlobUpload(BaseHandler):
    """ upload to cloudstorage and save serving_url in BlobFiles """

    def get(self):
        """ upload form """

        self.render_template('blob_upload.html', use_blobstore=blob_files.config.USE_BLOBSTORE)

    def readme(self):
        """ readme.md to html in base template """

        if self.request.method == 'GET':
            use_blobstore = blob_files.config.USE_BLOBSTORE
        else:  # POST
            use_blobstore = (True if self.request.get('use_blobstore') == 'T' else False)
        readme = markdown.markdown(open(README, 'r').read(), output_format='html5')  # options: markdown.__init__
        self.render_template('blob_upload.html', use_blobstore=use_blobstore, readme=readme)

    @ndb.synctasklet
    def post(self):
        """ upload the file. Result: show file and archive links """

        context = dict(failed='No file data', use_blobstore=(True if self.request.get('use_blobstore') == 'T' else False), files=[])

        # read upload data, save it in GCS and a zip archive
        file_data = self.request.get_all("file", default_value=None)
        if file_data:
            files = self.request.POST.getall('file')
            for index, fi in enumerate(files):

                filename = fi.filename.replace(':', '/')  # Fixes an issue with Mac OS where
                # slashes in the filename are parsed as colons
                folder = '/' + filename[:filename.rfind('/')]
                bf = blob_files.BlobFiles.new(filename.rsplit('/').pop(), folder=folder)
                bf.blob_write(file_data[index])
                bf.put_async()
                logging.info('Uploaded and saved in default GCS bucket : ' + bf.gcs_filename)

                context.update(
                    dict(failed=None, files=context['files'] + [(bf.serving_url, bf.filename)]))
        else:
            logging.warning('No file data')

        self.render_template('blob_links.html', **context)


routes = [
    webapp2.Route(r'/blob_upload', handler=BlobUpload),
    webapp2.Route(r'/readme', handler='blob_upload.BlobUpload:readme'),
    ('/use_blobstore/([^/]+)?', blob_serve.UseBlobstore),
    webapp2.Route('/', webapp2.RedirectHandler, defaults={
        '_uri': '/blob_upload'
    }),
]
app = ndb.toplevel(webapp2.WSGIApplication(routes=routes, debug=True))