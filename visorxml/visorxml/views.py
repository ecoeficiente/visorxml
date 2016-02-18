#!/usr/bin/env python
#encoding:utf8
#
# Copyright (c) 2015 Ministerio de Fomento
#                    Instituto de Ciencias de la Construcción Eduardo Torroja (IETcc-CSIC)
# 
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
# 

import base64
import logging
import os.path
from datetime import date, datetime
from io import BytesIO, StringIO

from django.conf import settings
from django.core.urlresolvers import reverse_lazy
from django.http import HttpResponseRedirect, HttpResponse
from django.template.loader import render_to_string
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import TemplateView, View

from extra_views import FormSetView
from PIL import Image

from .forms import XMLFileForm
from .reports import XMLReport
from .pdf_utils import render_to_pdf, get_xml_string_from_pdf
import string
import random


logger = logging.getLogger(__name__)


def load_report(session):
    file_name = session['report_xml_name']
    file_path = os.path.join(settings.MEDIA_ROOT, file_name)
    with open(file_path, 'rb') as xmlfile:
        report = XMLReport([(file_name, xmlfile.read())])
        return report


def random_name(size=20, ext=".xml"):
    return "".join([random.choice(string.ascii_letters + string.digits) for n in range(size)]) + ext


class HomeView(TemplateView):
    template_name = "home.html"


class ValidatorView(FormSetView):
    template_name = "validator.html"
    form_class = XMLFileForm
    extra = 2
    success_url = reverse_lazy('validator')

    def formset_valid(self, formset):
        session = self.request.session

        xml_files = []
        for form_index, form in enumerate(formset.forms):
            uploaded_file = form.cleaned_data.get('file', None)
            if uploaded_file:
                xml_files.append(uploaded_file)


        xml_strings = self.get_xml_strings(xml_files)
        report = XMLReport(xml_strings)

        print(report.errors['validation_errors'])
        if len(report.errors.get('validation_errors', None)) == 0:
            report_file = report.save_to_file()
            session['report_xml_name'] = report_file

        context_data = self.get_context_data(formset=formset)
        context_data['validation_data'] = report.errors

        return self.render_to_response(context_data)

    def get_xml_strings(self, xml_files):
        """
        Get a list of uploaded XML files and save some data in the user session.
        Returns a list of tuples, [(file_name, xml_file_content), ...]
        """
        xml_strings = []

        for new_file in xml_files:
            xml_string = ""
            if os.path.splitext(new_file.name)[1] == ".pdf":
                xml_string = get_xml_string_from_pdf(new_file)

            elif os.path.splitext(new_file.name)[1] == ".xml":
                xml_string = new_file.read()

            xml_strings.append((new_file.name, xml_string))


        return xml_strings


class GetXMLView(View):
    def get(self, request, *args, **kwargs):
        session = self.request.session
        file_name = session['report_xml_name']
        file_path = os.path.join(settings.MEDIA_ROOT, file_name)
        output_file_name = 'certificado-%s.xml' % datetime.now().strftime('%Y%m%d%H%M')

        with open(file_path, 'rb') as xmlfile:
            response = HttpResponse(xmlfile.read(), content_type='application/xml')
            response['Content-Disposition'] = 'attachment;filename=%s' % output_file_name
            return response


class EnergyPerformanceCertificateView(TemplateView):
    template_name = "energy-performance-certificate.html"

    def get(self, request, *args, **kwargs):
        session = request.session
        if session.get('report_xml_name', False):
            return super(EnergyPerformanceCertificateView, self).get(request, *args, **kwargs)
        else:
            return HttpResponseRedirect(reverse_lazy('validator'))

    def get_context_data(self, **kwargs):
        context = super(EnergyPerformanceCertificateView, self).get_context_data(**kwargs)
        report = load_report(self.request.session)

        espacios = zip(report.data.CondicionesFuncionamientoyOcupacion,
                       report.data.InstalacionesIluminacion.Espacios)

        context['report'] = report
        context['espacios'] = espacios

        return context


class EnergyPerformanceCertificatePDFView(EnergyPerformanceCertificateView):
    def render_to_response(self, context, **response_kwargs):
        session = self.request.session
        filename = 'certificado-%s.pdf' % datetime.now().strftime('%Y%m%d%H%M')

        html = render_to_string(self.template_name, context)

        env = {
            'generation_date': context['report'].data.DatosDelCertificador.Fecha,
            'reference': context['report'].data.IdentificacionEdificio.ReferenciaCatastral
        }
        xml_name = session['report_xml_name']
        xml_path = os.path.join(settings.MEDIA_ROOT, xml_name)
        return render_to_pdf(html, filename, xml_path, env)


class SupplementaryReportView(EnergyPerformanceCertificateView):
    template_name = "supplementary-report.html"


class SupplementaryReportPDFView(EnergyPerformanceCertificatePDFView):
    template_name = "supplementary-report.html"


class UpdateXMLView(View):
    def post(self, request, *args, **kwargs):
        element = request.POST['name']
        value = request.POST['value']

        report = load_report(self.request.session)
        report.update_element(element, value)

        return HttpResponse()

    @csrf_exempt
    def dispatch(self, *args, **kwargs):
        return super(UpdateXMLView, self).dispatch(*args, **kwargs)



class UploadImageView(View):
    def post(self, request, *args, **kwargs):
        uploaded_image = request.FILES['image']
        section = request.POST['section']

        #Read and resize the image
        image = Image.open(BytesIO(uploaded_image.read()))
        maxsize = (460, 460)
        image.thumbnail(maxsize, Image.ANTIALIAS)

        #Convert the image to a base64 string
        image_buffer = BytesIO()
        image.save(image_buffer, format="PNG")
        image_string = base64.b64encode(image_buffer.getvalue())

        report = load_report(self.request.session)
        report.update_image(section, image_string)

        return HttpResponse()

    @csrf_exempt
    def dispatch(self, *args, **kwargs):
        return super(UploadImageView, self).dispatch(*args, **kwargs)


